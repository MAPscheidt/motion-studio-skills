#!/usr/bin/env python3
"""
Motion Studio Pro — Reference Video Deconstruction Helper

Deconstructs reference motion graphics and video clips into:
- Metadata readout (info.txt, JSON format)
- Timestamped contact sheets (sheet_00.jpg, labeled with seconds)
- Consecutive hook frame strip (strip_hook.jpg, first 3 seconds)
- Automated scene cut detection (cuts.txt)
- Audio waveform and spectrogram (spectrogram.png, audio.wav)
- Motion summary metrics (analysis.json)

Zero external dependencies required (uses Python 3 stdlib + FFmpeg/ffprobe; optional Pillow for canvas labels).
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
import re
import math
from pathlib import Path
from fractions import Fraction

def find_binary(name):
    env_override = os.environ.get(f"{name.upper()}_PATH")
    if env_override and os.path.isfile(env_override):
        return env_override
    found = shutil.which(name)
    if found:
        return found
    # Common default paths on macOS / Linux / Windows
    for fallback in [
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/bin/{name}",
        f"/usr/bin/{name}",
        f"C:\\Program Files\\ffmpeg\\bin\\{name}.exe",
        f"C:\\ffmpeg\\bin\\{name}.exe",
    ]:
        if os.path.isfile(fallback):
            return fallback
    return None

def main():
    parser = argparse.ArgumentParser(
        description="Deconstruct reference video footage into timestamped contact sheets and motion metrics."
    )
    parser.add_argument("ref", help="Path to reference video file (.mp4, .mov, .webm, etc.)")
    parser.add_argument("--dur", type=float, default=15.0, help="Duration in seconds to analyze (default: 15.0)")
    parser.add_argument("--start", type=float, default=0.0, help="Start offset in seconds (default: 0.0)")
    parser.add_argument("--fps", type=float, default=4.0, help="Frame sampling rate for contact sheets (default: 4.0)")
    parser.add_argument("--hook", type=float, default=3.0, help="Consecutive hook duration in seconds (default: 3.0)")
    parser.add_argument("--out", type=str, default=None, help="Output directory (default: cache/ref_<name>)")

    args = parser.parse_args()

    # Validate inputs
    if not all(math.isfinite(x) for x in [args.dur, args.start, args.fps, args.hook]):
        sys.exit("Error: All numeric arguments must be finite numbers.")
    if args.dur <= 0 or args.fps <= 0 or args.start < 0 or args.hook < 0:
        sys.exit("Error: Duration and FPS must be positive; start and hook duration cannot be negative.")

    ref_path = Path(args.ref).resolve()
    if not ref_path.is_file():
        sys.exit(f"Error: Reference video not found at '{ref_path}'.")

    # Resolve FFmpeg binaries
    ffmpeg = find_binary("ffmpeg")
    ffprobe = find_binary("ffprobe")
    if not ffmpeg:
        sys.exit("Error: 'ffmpeg' not found on PATH. Please install FFmpeg (e.g. brew install ffmpeg).")
    if not ffprobe:
        sys.exit("Error: 'ffprobe' not found on PATH. Please install FFmpeg (which includes ffprobe).")

    # Output directory
    clean_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", ref_path.stem)[:40]
    out_dir = Path(args.out or f"cache/ref_{clean_stem}").resolve()
    if ref_path.is_relative_to(out_dir):
        sys.exit("Error: Input file must reside outside the analysis output directory.")

    out_f_dir = out_dir / "f"
    out_hook_dir = out_dir / "hook"
    for d in [out_dir, out_f_dir, out_hook_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Clean existing generated artifacts
    for f in list(out_f_dir.glob("*.jpg")) + list(out_hook_dir.glob("*.jpg")) + list(out_dir.glob("sheet_*.jpg")):
        try:
            f.unlink()
        except OSError:
            pass
    for name in ["strip_hook.jpg", "spectrogram.png", "audio.wav", "info.txt", "cuts.txt", "analysis.json"]:
        (out_dir / name).unlink(missing_ok=True)

    def run_cmd(cmd_args):
        res = subprocess.run(cmd_args, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"Command failed (code {res.returncode}):\n{res.stderr[-1000:]}")
        return res

    # 1. Probe video streams
    probe_res = run_cmd([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(ref_path)])
    probe_data = json.loads(probe_res.stdout)
    video_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video_stream:
        sys.exit("Error: Reference file contains no video stream.")
    has_audio = any(s.get("codec_type") == "audio" for s in probe_data.get("streams", []))

    (out_dir / "info.txt").write_text(json.dumps(probe_data, indent=2), encoding="utf-8")

    # Native video FPS calculation
    try:
        r_rate = video_stream.get("r_frame_rate", "30/1")
        fps_src = float(Fraction(r_rate))
    except (ValueError, ZeroDivisionError):
        fps_src = 30.0
    if fps_src <= 0:
        fps_src = 30.0

    width = int(video_stream.get("width", 720))
    height = int(video_stream.get("height", 1280))
    aspect_ratio_str = f"{width}:{height}"

    ss_args = ["-ss", str(args.start)] if args.start > 0 else []
    base_in = [ffmpeg, "-v", "error", "-y"] + ss_args + ["-t", str(args.dur), "-i", str(ref_path)]

    print(f"Analyzing reference: {ref_path.name}")
    print(f"Format: {width}x{height} @ {fps_src:.2f} FPS (Audio: {'Yes' if has_audio else 'None'})")
    print(f"Window: start={args.start:.2f}s, dur={args.dur:.2f}s")

    # 2. Extract sampled frames for contact sheet
    run_cmd(base_in + ["-map", "0:v:0", "-an", "-vf", f"fps={args.fps},scale=360:-2", str(out_f_dir / "%04d.jpg")])

    # 3. Extract consecutive frames for hook strip
    hook_dur = min(args.hook, args.dur)
    if hook_dur > 0:
        run_cmd(base_in + ["-t", str(hook_dur), "-map", "0:v:0", "-an", "-vf", "scale=360:-2", str(out_hook_dir / "%04d.jpg")])

    # 4. Generate Contact Sheets
    def build_contact_sheet(image_files, target_path, labels, cols=6):
        if not image_files:
            return
        rows = (len(image_files) + cols - 1) // cols
        try:
            from PIL import Image, ImageDraw
            has_pil = True
        except ImportError:
            has_pil = False

        if not has_pil:
            print("Notice: Pillow not installed. Generating unlabelled contact sheet via FFmpeg.")
            run_cmd([
                ffmpeg, "-v", "error", "-y",
                "-start_number", str(int(image_files[0].stem)),
                "-i", str(image_files[0].parent / "%04d.jpg"),
                "-vf", f"tile={cols}x{rows}:nb_frames={len(image_files)}:padding=4:color=0x15161b",
                "-frames:v", "1", str(target_path)
            ])
            return

        with Image.open(image_files[0]) as im0:
            iw, ih = im0.size

        label_h = 24
        cw = cols * (iw + 6) + 6
        ch = rows * (ih + label_h + 6) + 6
        canvas = Image.new("RGB", (cw, ch), (21, 22, 27))
        draw = ImageDraw.Draw(canvas)

        for idx, (img_path, label) in enumerate(zip(image_files, labels)):
            c_idx = idx % cols
            r_idx = idx // cols
            x = 6 + c_idx * (iw + 6)
            y = 6 + r_idx * (ih + label_h + 6)
            with Image.open(img_path) as im:
                canvas.paste(im.convert("RGB"), (x, y))
            draw.text((x + 4, y + ih + 4), label, fill=(220, 225, 235))

        canvas.save(target_path, quality=90)

    sampled_files = sorted(out_f_dir.glob("*.jpg"))
    sheet_count = 0
    for chunk_start in range(0, len(sampled_files), 24):
        chunk_files = sampled_files[chunk_start:chunk_start + 24]
        chunk_labels = [f"{args.start + (chunk_start + j) / args.fps:.3f}s" for j in range(len(chunk_files))]
        sheet_path = out_dir / f"sheet_{sheet_count:02d}.jpg"
        build_contact_sheet(chunk_files, sheet_path, chunk_labels, cols=6)
        sheet_count += 1

    hook_files = sorted(out_hook_dir.glob("*.jpg"))
    if hook_files:
        hook_labels = [f"{args.start + j / fps_src:.3f}s" for j in range(len(hook_files))]
        build_contact_sheet(hook_files, out_dir / "strip_hook.jpg", hook_labels, cols=min(8, len(hook_files)))

    # 5. Scene Cut Detection
    detect_res = subprocess.run(
        [ffmpeg, "-hide_banner"] + ss_args + ["-t", str(args.dur), "-i", str(ref_path), "-an", "-vf", "select='gt(scene,0.3)',showinfo", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    raw_cuts = [args.start + float(x) for x in re.findall(r"pts_time:([0-9.eE+-]+)", detect_res.stderr)]
    cut_timestamps = sorted(list(set(round(c, 3) for c in raw_cuts)))
    (out_dir / "cuts.txt").write_text("\n".join(f"{c:.3f}s" for c in cut_timestamps) + "\n", encoding="utf-8")

    # 6. Audio Spectrogram & Extraction
    if has_audio:
        run_cmd(base_in + ["-lavfi", "showspectrumpic=s=1200x360:legend=1:scale=log:fscale=log:color=fire", "-frames:v", "1", str(out_dir / "spectrogram.png")])
        run_cmd(base_in + ["-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", str(out_dir / "audio.wav")])

    # 7. Summary metrics
    avg_cut_dur = args.dur / max(1, len(cut_timestamps) + 1)
    summary = {
        "source": ref_path.name,
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio_str,
        "fps_source": fps_src,
        "start": args.start,
        "duration": args.dur,
        "sample_fps": args.fps,
        "total_sampled_frames": len(sampled_files),
        "contact_sheets": sheet_count,
        "hook_frames": len(hook_files),
        "scene_cuts": cut_timestamps,
        "scene_count": len(cut_timestamps) + 1,
        "average_scene_duration_sec": round(avg_cut_dur, 2),
        "has_audio": has_audio,
        "recommended_pacing": "hyper" if avg_cut_dur < 1.2 else ("medium" if avg_cut_dur < 2.5 else "restrained"),
    }
    (out_dir / "analysis.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Deconstruction complete: {out_dir}")
    print(f"Sheets: {sheet_count} | Hook frames: {len(hook_files)} | Detected cuts: {len(cut_timestamps)}")
    print(f"Summary metrics saved to {out_dir / 'analysis.json'}")

if __name__ == "__main__":
    main()
