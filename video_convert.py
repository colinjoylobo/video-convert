#!/usr/bin/env python3
"""Video conversion & processing tool — format, resolution, codec, effects, and more.

Usage:
    # Basic conversion
    python video_convert.py input.mov                              # MOV -> MP4
    python video_convert.py input.mov -f webm                      # MOV -> WebM
    python video_convert.py input.mov -r 1080                      # Downscale to 1080p
    python video_convert.py input.mov -r 4k                        # Upscale to 4K
    python video_convert.py input.mov -r 1280x720                  # Custom resolution
    python video_convert.py input.mov -r 50%                       # Scale by percentage
    python video_convert.py input.mov -vc h265 -ac aac             # Change codecs

    # Trim & speed
    python video_convert.py input.mov --trim 0:30-1:45             # Cut segment
    python video_convert.py input.mov --trim 10-30                  # Seconds 10 to 30
    python video_convert.py input.mov --speed 2                     # 2x speed
    python video_convert.py input.mov --speed 0.5                   # Slow motion
    python video_convert.py input.mov --reverse                     # Reverse video

    # Visual effects
    python video_convert.py input.mov --stabilize                   # Stabilize shaky video
    python video_convert.py input.mov --denoise                     # Remove noise
    python video_convert.py input.mov --sharpen                     # Sharpen
    python video_convert.py input.mov --fade 1.5                    # Fade in/out 1.5s
    python video_convert.py input.mov --rotate 90                   # Rotate 90/180/270
    python video_convert.py input.mov --hflip                       # Horizontal flip
    python video_convert.py input.mov --vflip                       # Vertical flip
    python video_convert.py input.mov --crop 16:9                   # Crop to aspect ratio
    python video_convert.py input.mov --crop 500:500:100:100        # Crop w:h:x:y
    python video_convert.py input.mov --autocrop                    # Auto-remove black bars
    python video_convert.py input.mov --lut film.cube               # Apply color LUT

    # Color & brightness
    python video_convert.py input.mov --brightness 0.1              # -1.0 to 1.0
    python video_convert.py input.mov --contrast 1.2                # 0.0 to 2.0
    python video_convert.py input.mov --saturation 1.3              # 0.0 to 3.0
    python video_convert.py input.mov --gamma 1.5                   # 0.1 to 10.0
    python video_convert.py input.mov --hdr-to-sdr                  # HDR tonemapping

    # Audio
    python video_convert.py input.mov --no-audio                    # Strip audio
    python video_convert.py input.mov --normalize                   # Normalize audio (EBU R128)
    python video_convert.py input.mov --volume 1.5                  # Volume multiplier
    python video_convert.py input.mov --extract-audio               # Rip audio to file
    python video_convert.py input.mov --audio-fade 2                # Audio fade in/out

    # Overlay & watermark
    python video_convert.py input.mov --watermark logo.png          # Add image watermark
    python video_convert.py input.mov --watermark logo.png:br:0.5   # Bottom-right, 50% opacity
    python video_convert.py input.mov --text "Sample" --text-pos tc # Burn text overlay
    python video_convert.py input.mov --subs captions.srt           # Burn in subtitles

    # Thumbnails & previews
    python video_convert.py input.mov --thumbnail 5                 # Frame at 5s
    python video_convert.py input.mov --contact-sheet 4x4           # 4x4 thumbnail grid
    python video_convert.py input.mov --gif-preview 3-8             # GIF from 3s to 8s

    # Platform presets
    python video_convert.py input.mov --preset youtube              # YouTube optimized
    python video_convert.py input.mov --preset twitter              # Twitter limits
    python video_convert.py input.mov --preset discord              # Discord 25MB limit
    python video_convert.py input.mov --preset instagram-reels      # 9:16 vertical
    python video_convert.py input.mov --preset whatsapp             # Compressed for WhatsApp
    python video_convert.py input.mov --preset web                  # Max compatibility

    # Advanced
    python video_convert.py input.mov --target-size 25              # Fit in 25 MB
    python video_convert.py input.mov --faststart                   # Web streaming optimize
    python video_convert.py input.mov --loop 3                      # Loop video 3 times
    python video_convert.py input.mov --concat b.mov c.mov          # Join videos
    python video_convert.py input.mov --copy                        # Remux only, no re-encode
    python video_convert.py input.mov --dry-run                     # Show ffmpeg command only

    # Batch & upload
    python video_convert.py /path/to/folder/ -r 1080 -f mp4        # Batch convert folder
    python video_convert.py input.mov --s3                          # Convert + upload to S3
    python video_convert.py input.mov --info                        # Show video info
"""

import os
import sys
import json
import math
import shutil
import tempfile
import argparse
import subprocess
from pathlib import Path

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.mts', '.ts', '.gif'}

RESOLUTION_PRESETS = {
    '360':  (640, 360),
    '480':  (854, 480),
    '720':  (1280, 720),
    'hd':   (1920, 1080),
    '1080': (1920, 1080),
    '2k':   (2560, 1440),
    '1440': (2560, 1440),
    '4k':   (3840, 2160),
    '2160': (3840, 2160),
    '8k':   (7680, 4320),
}

VCODEC_MAP = {
    'h264': 'libx264', 'x264': 'libx264',
    'h265': 'libx265', 'x265': 'libx265', 'hevc': 'libx265',
    'vp9':  'libvpx-vp9',
    'av1':  'libsvtav1',
    'prores': 'prores_ks',
    'copy': 'copy',
}

ACODEC_MAP = {
    'aac': 'aac', 'opus': 'libopus', 'mp3': 'libmp3lame',
    'flac': 'flac', 'copy': 'copy', 'none': None,
}

FORMAT_DEFAULTS = {
    'mp4':  ('libx264', 'aac'),
    'webm': ('libvpx-vp9', 'libopus'),
    'mkv':  ('libx264', 'aac'),
    'avi':  ('libx264', 'mp3'),
    'mov':  ('libx264', 'aac'),
    'gif':  (None, None),
}

PLATFORM_PRESETS = {
    'youtube': {
        'fmt': 'mp4', 'vcodec': 'h264', 'acodec': 'aac', 'quality': 16,
        'faststart': True, 'extra_args': ['-profile:v', 'high', '-level', '4.2'],
    },
    'twitter': {
        'fmt': 'mp4', 'vcodec': 'h264', 'acodec': 'aac', 'quality': 20,
        'faststart': True, 'max_res': (1920, 1080),
    },
    'discord': {
        'fmt': 'mp4', 'vcodec': 'h264', 'acodec': 'aac',
        'target_size_mb': 25, 'faststart': True,
    },
    'instagram-reels': {
        'fmt': 'mp4', 'vcodec': 'h264', 'acodec': 'aac', 'quality': 18,
        'faststart': True, 'crop_aspect': '9:16', 'max_res': (1080, 1920),
    },
    'instagram-feed': {
        'fmt': 'mp4', 'vcodec': 'h264', 'acodec': 'aac', 'quality': 18,
        'faststart': True, 'crop_aspect': '1:1', 'max_res': (1080, 1080),
    },
    'tiktok': {
        'fmt': 'mp4', 'vcodec': 'h264', 'acodec': 'aac', 'quality': 18,
        'faststart': True, 'crop_aspect': '9:16', 'max_res': (1080, 1920),
    },
    'whatsapp': {
        'fmt': 'mp4', 'vcodec': 'h264', 'acodec': 'aac',
        'target_size_mb': 16, 'faststart': True, 'max_res': (1280, 720),
    },
    'web': {
        'fmt': 'mp4', 'vcodec': 'h264', 'acodec': 'aac', 'quality': 20,
        'faststart': True, 'extra_args': ['-profile:v', 'baseline', '-pix_fmt', 'yuv420p'],
    },
    'archive': {
        'fmt': 'mkv', 'vcodec': 'h265', 'acodec': 'flac', 'quality': 14,
    },
}


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def _run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def _human_size(nbytes):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} PB"


def _parse_time(t):
    """Parse time string like '1:30', '90', '0:01:30.5' to seconds."""
    t = t.strip()
    parts = t.split(':')
    if len(parts) == 1:
        return float(parts[0])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    raise ValueError(f"Invalid time: {t}")


def _fmt_time(secs):
    """Format seconds to HH:MM:SS.mmm."""
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = secs % 60
    return f"{h}:{m:02d}:{s:06.3f}"


# ── Info ──────────────────────────────────────────────────────────────

def get_info(filepath):
    """Get video file info as a dict."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', filepath
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return json.loads(result.stdout)


def _get_video_stream(info):
    for s in info.get('streams', []):
        if s['codec_type'] == 'video':
            return s
    return {}


def _get_duration(info):
    fmt = info.get('format', {})
    return float(fmt.get('duration', 0))


def print_info(filepath):
    """Print human-readable video info."""
    info = get_info(filepath)
    fmt = info.get('format', {})
    _log(f"\nFile: {Path(filepath).name}")
    _log(f"Format: {fmt.get('format_long_name', '?')}")
    duration = float(fmt.get('duration', 0))
    _log(f"Duration: {int(duration//60)}m {int(duration%60)}s ({duration:.2f}s)")
    size = int(fmt.get('size', 0))
    _log(f"Size: {_human_size(size)}")
    bitrate = int(fmt.get('bit_rate', 0))
    _log(f"Bitrate: {bitrate // 1000} kbps")

    for stream in info.get('streams', []):
        if stream['codec_type'] == 'video':
            w, h = stream.get('width', '?'), stream.get('height', '?')
            codec = stream.get('codec_name', '?')
            fps = stream.get('r_frame_rate', '?')
            if '/' in str(fps):
                num, den = fps.split('/')
                fps = f"{int(num)/int(den):.2f}"
            pix_fmt = stream.get('pix_fmt', '?')
            _log(f"Video: {w}x{h} | {codec} | {fps} fps | {pix_fmt}")
        elif stream['codec_type'] == 'audio':
            codec = stream.get('codec_name', '?')
            sr = stream.get('sample_rate', '?')
            ch = stream.get('channels', '?')
            _log(f"Audio: {codec} | {sr} Hz | {ch}ch")
    _log("")


# ── Resolution ────────────────────────────────────────────────────────

def _parse_resolution(res_str, src_w, src_h):
    if not res_str:
        return None
    res_str = res_str.lower().strip()
    if res_str in RESOLUTION_PRESETS:
        return RESOLUTION_PRESETS[res_str]
    if res_str.endswith('%'):
        pct = float(res_str[:-1]) / 100
        w, h = int(src_w * pct), int(src_h * pct)
        return (w + (w % 2), h + (h % 2))
    if 'x' in res_str:
        parts = res_str.split('x')
        return (int(parts[0]), int(parts[1]))
    try:
        target_h = int(res_str)
        target_w = int(src_w * (target_h / src_h))
        return (target_w + (target_w % 2), target_h)
    except ValueError:
        raise ValueError(f"Unknown resolution: {res_str}")


def _crop_to_aspect(src_w, src_h, aspect_str):
    """Calculate crop filter for target aspect ratio. Returns crop string."""
    parts = aspect_str.split(':')
    aw, ah = int(parts[0]), int(parts[1])
    target_ratio = aw / ah
    src_ratio = src_w / src_h

    if abs(target_ratio - src_ratio) < 0.01:
        return None  # already correct

    if target_ratio > src_ratio:
        # wider target: crop height
        new_h = int(src_w / target_ratio)
        new_h = new_h - (new_h % 2)
        y = (src_h - new_h) // 2
        return f"crop={src_w}:{new_h}:0:{y}"
    else:
        # taller target: crop width
        new_w = int(src_h * target_ratio)
        new_w = new_w - (new_w % 2)
        x = (src_w - new_w) // 2
        return f"crop={new_w}:{src_h}:{x}:0"


# ── Stabilization (two-pass) ─────────────────────────────────────────

def _stabilize_detect(filepath):
    """Run vidstab detection pass. Returns path to transforms file."""
    transforms = tempfile.NamedTemporaryFile(suffix='.trf', delete=False)
    transforms.close()
    _log("Stabilize: analyzing motion (pass 1/2)...")
    cmd = [
        'ffmpeg', '-nostdin', '-i', filepath,
        '-vf', f'vidstabdetect=shakiness=5:accuracy=15:result={transforms.name}',
        '-f', 'null', '-'
    ]
    result = _run(cmd)
    if result.returncode != 0:
        os.unlink(transforms.name)
        raise RuntimeError(f"Stabilization detect failed:\n{result.stderr[-300:]}")
    return transforms.name


# ── Auto-crop detection ──────────────────────────────────────────────

def _detect_crop(filepath):
    """Detect black bars and return crop filter string."""
    _log("Detecting black bars...")
    cmd = [
        'ffmpeg', '-nostdin', '-i', filepath,
        '-vf', 'cropdetect=24:16:0', '-t', '60',
        '-f', 'null', '-'
    ]
    result = _run(cmd)
    crops = []
    for line in result.stderr.split('\n'):
        if 'crop=' in line:
            idx = line.index('crop=')
            crop = line[idx:].split()[0]
            crops.append(crop)
    if crops:
        # Most common crop value
        from collections import Counter
        most_common = Counter(crops).most_common(1)[0][0]
        _log(f"Detected: {most_common}")
        return most_common
    return None


# ── Audio normalization (two-pass) ───────────────────────────────────

def _detect_loudnorm(filepath):
    """Run loudnorm analysis pass. Returns measured parameters."""
    _log("Analyzing audio levels (pass 1/2)...")
    cmd = [
        'ffmpeg', '-nostdin', '-i', filepath,
        '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json',
        '-f', 'null', '-'
    ]
    result = _run(cmd)
    # Extract JSON block from stderr
    stderr = result.stderr
    try:
        json_start = stderr.rindex('{')
        json_end = stderr.index('}', json_start) + 1
        return json.loads(stderr[json_start:json_end])
    except (ValueError, json.JSONDecodeError):
        return None


# ── Thumbnail / Contact sheet ────────────────────────────────────────

def extract_thumbnail(filepath, time_sec=None, output=None):
    """Extract a single frame as an image."""
    info = get_info(filepath)
    duration = _get_duration(info)
    if time_sec is None:
        time_sec = duration * 0.1  # 10% in by default
    src = Path(filepath)
    if output is None:
        output = str(src.with_suffix('.jpg'))
    cmd = [
        'ffmpeg', '-nostdin', '-ss', str(time_sec), '-i', filepath,
        '-frames:v', '1', '-q:v', '2', '-y', output
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"Thumbnail failed:\n{result.stderr[-300:]}")
    _log(f"Thumbnail: {Path(output).name}")
    return output


def create_contact_sheet(filepath, grid='4x4', output=None):
    """Create a thumbnail contact sheet grid."""
    info = get_info(filepath)
    duration = _get_duration(info)
    cols, rows = [int(x) for x in grid.split('x')]
    total = cols * rows
    interval = duration / (total + 1)

    src = Path(filepath)
    if output is None:
        output = str(src.with_stem(src.stem + '_contact').with_suffix('.jpg'))

    cmd = [
        'ffmpeg', '-nostdin', '-i', filepath,
        '-vf', f"select='not(mod(n\\,{int(interval * 24)}))',scale=320:-1,tile={cols}x{rows}",
        '-frames:v', '1', '-q:v', '2', '-y', output
    ]
    # Better approach: use fps filter
    fps_val = total / duration
    cmd = [
        'ffmpeg', '-nostdin', '-i', filepath,
        '-vf', f"fps=1/{interval:.2f},scale=320:-1,tile={cols}x{rows}",
        '-frames:v', '1', '-q:v', '2', '-y', output
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"Contact sheet failed:\n{result.stderr[-300:]}")
    _log(f"Contact sheet ({grid}): {Path(output).name}")
    return output


def create_gif_preview(filepath, time_range=None, resolution='480', fps_val=12, output=None):
    """Create an animated GIF preview clip."""
    src = Path(filepath)
    if output is None:
        output = str(src.with_stem(src.stem + '_preview').with_suffix('.gif'))

    cmd = ['ffmpeg', '-nostdin']
    if time_range:
        parts = time_range.split('-')
        start = _parse_time(parts[0])
        end = _parse_time(parts[1])
        cmd += ['-ss', str(start), '-t', str(end - start)]
    cmd += ['-i', filepath]

    info = get_info(filepath)
    vs = _get_video_stream(info)
    src_w, src_h = vs.get('width', 1920), vs.get('height', 1080)
    target_res = _parse_resolution(str(resolution), src_w, src_h)

    scale = f"scale={target_res[0]}:{target_res[1]}" if target_res else "scale=480:-1"
    cmd += [
        '-vf', f"{scale},fps={fps_val},split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
        '-y', output
    ]
    _log(f"Creating GIF preview...")
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"GIF preview failed:\n{result.stderr[-300:]}")
    _log(f"GIF preview: {Path(output).name} ({_human_size(os.path.getsize(output))})")
    return output


# ── Target size calculation ──────────────────────────────────────────

def _calc_bitrate_for_size(target_mb, duration, audio_bitrate_kbps=192):
    """Calculate video bitrate to hit target file size."""
    target_bits = target_mb * 8 * 1024 * 1024
    audio_bits = audio_bitrate_kbps * 1000 * duration
    video_bits = target_bits - audio_bits
    if video_bits <= 0:
        raise ValueError(f"Target size {target_mb}MB too small for {duration:.0f}s video")
    return int(video_bits / duration / 1000)  # kbps


# ── Main convert function ────────────────────────────────────────────

def convert(filepath, fmt=None, resolution=None, vcodec=None, acodec=None,
            quality=18, fps=None, no_audio=False, output=None,
            trim=None, speed=None, reverse=False,
            stabilize=False, denoise=False, sharpen=False,
            fade=None, rotate=None, hflip=False, vflip=False,
            crop=None, autocrop=False, lut=None,
            brightness=None, contrast=None, saturation=None, gamma=None,
            hdr_to_sdr=False,
            normalize=False, volume=None, extract_audio=False, audio_fade=None,
            watermark=None, text=None, text_pos='bc', subs=None,
            target_size_mb=None, faststart=False, loop=None,
            copy=False, dry_run=False, extra_args=None,
            crop_aspect=None, max_res=None):
    """Convert a video file with full processing options. Returns output path."""
    filepath = os.path.expanduser(filepath)
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Not found: {filepath}")

    src = Path(filepath)

    # Extract audio mode
    if extract_audio:
        fmt = fmt or 'mp3'
        out_path = output or str(src.with_suffix(f'.{fmt}'))
        cmd = ['ffmpeg', '-nostdin', '-i', filepath]
        ac = ACODEC_MAP.get(fmt, fmt)
        if ac:
            cmd += ['-vn', '-c:a', ac]
        else:
            cmd += ['-vn']
        if fmt == 'mp3':
            cmd += ['-b:a', '320k']
        elif fmt == 'flac':
            pass  # lossless
        else:
            cmd += ['-b:a', '192k']
        cmd += ['-y', out_path]
        if dry_run:
            _log(f"Command: {' '.join(cmd)}")
            return out_path
        _log(f"Extracting audio: {src.name} -> {Path(out_path).name}")
        result = _run(cmd)
        if result.returncode != 0:
            raise RuntimeError(f"Audio extraction failed:\n{result.stderr[-500:]}")
        _log(f"Done: {Path(out_path).name} ({_human_size(os.path.getsize(out_path))})")
        return out_path

    # Determine output format
    if fmt is None:
        fmt = 'mp4'
    fmt = fmt.lower().lstrip('.')

    # Output path
    if output:
        out_path = output
    else:
        out_path = str(src.with_suffix(f'.{fmt}'))
        if out_path == str(src):
            out_path = str(src.with_stem(src.stem + '_converted').with_suffix(f'.{fmt}'))

    # Get source info
    info = get_info(filepath)
    vs = _get_video_stream(info)
    src_w = vs.get('width', 0)
    src_h = vs.get('height', 0)
    duration = _get_duration(info)

    # ── Build ffmpeg command ──────────────────────────────────────────

    cmd = ['ffmpeg', '-nostdin']
    input_args = []
    vf_parts = []
    af_parts = []
    post_args = []

    # Trim
    if trim:
        parts = trim.split('-')
        start = _parse_time(parts[0])
        input_args += ['-ss', str(start)]
        if len(parts) > 1:
            end = _parse_time(parts[1])
            input_args += ['-t', str(end - start)]
            duration = end - start

    # Loop input
    if loop:
        input_args += ['-stream_loop', str(int(loop) - 1)]
        duration *= int(loop)

    cmd += input_args + ['-i', filepath]

    # Copy mode (remux only)
    if copy:
        cmd += ['-c', 'copy']
        if faststart and fmt == 'mp4':
            cmd += ['-movflags', '+faststart']
        cmd += ['-y', out_path]
        if dry_run:
            _log(f"Command: {' '.join(cmd)}")
            return out_path
        _log(f"Remuxing: {src.name} -> {Path(out_path).name}")
        result = _run(cmd)
        if result.returncode != 0:
            raise RuntimeError(f"Remux failed:\n{result.stderr[-500:]}")
        _log(f"Done: {_human_size(os.path.getsize(out_path))}")
        return out_path

    # ── Watermark input ──────────────────────────────────────────────
    wm_input = False
    if watermark:
        wm_parts = watermark.split(':')
        wm_file = wm_parts[0]
        wm_pos = wm_parts[1] if len(wm_parts) > 1 else 'br'
        wm_opacity = float(wm_parts[2]) if len(wm_parts) > 2 else 0.7
        cmd += ['-i', wm_file]
        wm_input = True

    # ── Video filters ────────────────────────────────────────────────

    # Stabilization (two-pass)
    transforms_file = None
    if stabilize:
        transforms_file = _stabilize_detect(filepath)
        vf_parts.append(f"vidstabtransform=smoothing=10:input={transforms_file}")
        _log("Stabilize: applying transforms (pass 2/2)...")

    # Autocrop
    if autocrop:
        crop_filter = _detect_crop(filepath)
        if crop_filter:
            vf_parts.append(crop_filter)

    # Manual crop
    if crop:
        if ':' in crop and len(crop.split(':')) == 4:
            # w:h:x:y format
            vf_parts.append(f"crop={crop}")
        elif ':' in crop:
            # Aspect ratio crop
            cf = _crop_to_aspect(src_w, src_h, crop)
            if cf:
                vf_parts.append(cf)

    # Crop to aspect ratio (from preset)
    if crop_aspect and not crop:
        cf = _crop_to_aspect(src_w, src_h, crop_aspect)
        if cf:
            vf_parts.append(cf)

    # Rotation
    if rotate:
        r = int(rotate)
        if r == 90:
            vf_parts.append('transpose=1')
        elif r == 180:
            vf_parts.append('transpose=1,transpose=1')
        elif r == 270:
            vf_parts.append('transpose=2')
        else:
            vf_parts.append(f'rotate={r}*PI/180')

    # Flips
    if hflip:
        vf_parts.append('hflip')
    if vflip:
        vf_parts.append('vflip')

    # Resolution
    target_res = _parse_resolution(resolution, src_w, src_h)
    if max_res and not target_res:
        # Apply max resolution constraint
        if src_w > max_res[0] or src_h > max_res[1]:
            target_res = max_res
    if target_res:
        vf_parts.append(f'scale={target_res[0]}:{target_res[1]}:flags=lanczos')

    # Denoise
    if denoise:
        vf_parts.append('hqdn3d=4:4:3:3')

    # Sharpen
    if sharpen:
        vf_parts.append('cas=0.4')

    # Color adjustments
    eq_parts = []
    if brightness is not None:
        eq_parts.append(f'brightness={brightness}')
    if contrast is not None:
        eq_parts.append(f'contrast={contrast}')
    if saturation is not None:
        eq_parts.append(f'saturation={saturation}')
    if gamma is not None:
        eq_parts.append(f'gamma={gamma}')
    if eq_parts:
        vf_parts.append(f"eq={':'.join(eq_parts)}")

    # LUT
    if lut:
        vf_parts.append(f"lut3d={lut}")

    # HDR to SDR
    if hdr_to_sdr:
        vf_parts.append('zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p')

    # Speed
    if speed and speed != 1.0:
        vf_parts.append(f'setpts={1.0/speed}*PTS')
        # Audio tempo
        if not no_audio:
            s = float(speed)
            # atempo only supports 0.5-2.0, chain for more
            while s > 2.0:
                af_parts.append('atempo=2.0')
                s /= 2.0
            while s < 0.5:
                af_parts.append('atempo=0.5')
                s /= 0.5
            if 0.5 <= s <= 2.0:
                af_parts.append(f'atempo={s}')

    # Reverse
    if reverse:
        vf_parts.append('reverse')
        if not no_audio:
            af_parts.append('areverse')

    # Fade in/out
    if fade:
        fade_dur = float(fade)
        vf_parts.append(f'fade=t=in:st=0:d={fade_dur}')
        if duration > fade_dur:
            fade_out_start = duration - fade_dur
            vf_parts.append(f'fade=t=out:st={fade_out_start:.2f}:d={fade_dur}')

    # Subtitles burn-in
    if subs:
        # Escape special characters in path
        subs_escaped = subs.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")
        vf_parts.append(f"subtitles='{subs_escaped}'")

    # Text overlay
    if text:
        positions = {
            'tl': 'x=20:y=20',
            'tc': 'x=(w-text_w)/2:y=20',
            'tr': 'x=w-text_w-20:y=20',
            'bl': 'x=20:y=h-text_h-20',
            'bc': 'x=(w-text_w)/2:y=h-text_h-20',
            'br': 'x=w-text_w-20:y=h-text_h-20',
            'c':  'x=(w-text_w)/2:y=(h-text_h)/2',
        }
        pos = positions.get(text_pos, positions['bc'])
        vf_parts.append(
            f"drawtext=text='{text}':fontsize=48:fontcolor=white:"
            f"borderw=2:bordercolor=black:{pos}"
        )

    # ── Audio filters ────────────────────────────────────────────────

    # Audio normalization (two-pass)
    loudnorm_params = None
    if normalize:
        loudnorm_params = _detect_loudnorm(filepath)
        if loudnorm_params:
            lp = loudnorm_params
            af_parts.append(
                f"loudnorm=I=-16:TP=-1.5:LRA=11:"
                f"measured_I={lp.get('input_i', '-24')}:"
                f"measured_TP={lp.get('input_tp', '-2')}:"
                f"measured_LRA={lp.get('input_lra', '7')}:"
                f"measured_thresh={lp.get('input_thresh', '-34')}:"
                f"offset={lp.get('target_offset', '0')}:"
                f"linear=true:print_format=summary"
            )
            _log("Normalizing audio (pass 2/2)...")

    # Volume
    if volume is not None:
        af_parts.append(f'volume={volume}')

    # Audio fade
    if audio_fade:
        af_dur = float(audio_fade)
        af_parts.append(f'afade=t=in:st=0:d={af_dur}')
        if duration > af_dur:
            af_parts.append(f'afade=t=out:st={duration - af_dur:.2f}:d={af_dur}')

    # ── GIF special ──────────────────────────────────────────────────

    if fmt == 'gif':
        if not any('fps' in p for p in vf_parts):
            vf_parts.append(f'fps={fps or 15}')
        vf_parts.append('split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse')
        cmd += ['-vf', ','.join(vf_parts)]
        cmd += ['-y', out_path]
        if dry_run:
            _log(f"Command: {' '.join(cmd)}")
            return out_path
        _log(f"Converting: {src.name} -> {Path(out_path).name}")
        result = _run(cmd)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-500:]}")
        out_size = os.path.getsize(out_path)
        _log(f"Done: {_human_size(out_size)} ({Path(out_path).name})")
        return out_path

    # ── Watermark overlay (complex filter) ───────────────────────────

    if wm_input:
        # Build complex filter for watermark
        wm_positions = {
            'tl': 'x=20:y=20',
            'tc': 'x=(W-w)/2:y=20',
            'tr': 'x=W-w-20:y=20',
            'bl': 'x=20:y=H-h-20',
            'bc': 'x=(W-w)/2:y=H-h-20',
            'br': 'x=W-w-20:y=H-h-20',
            'c':  'x=(W-w)/2:y=(H-h)/2',
        }
        wm_xy = wm_positions.get(wm_pos, wm_positions['br'])

        # Pre-filters on main video
        pre_vf = ','.join(vf_parts) if vf_parts else None
        if pre_vf:
            complex_filter = f"[0:v]{pre_vf}[main];[1:v]format=rgba,colorchannelmixer=aa={wm_opacity}[wm];[main][wm]overlay={wm_xy}"
        else:
            complex_filter = f"[1:v]format=rgba,colorchannelmixer=aa={wm_opacity}[wm];[0:v][wm]overlay={wm_xy}"
        cmd += ['-filter_complex', complex_filter]
        vf_parts = []  # already in complex filter
    else:
        # Simple video filter chain
        if vf_parts:
            cmd += ['-vf', ','.join(vf_parts)]

    # Audio filters
    if af_parts and not no_audio:
        cmd += ['-af', ','.join(af_parts)]

    # ── Codecs ───────────────────────────────────────────────────────

    if vcodec:
        vc = VCODEC_MAP.get(vcodec.lower(), vcodec)
    else:
        vc = FORMAT_DEFAULTS.get(fmt, ('libx264', 'aac'))[0]

    if no_audio:
        ac = None
    elif acodec:
        ac_key = acodec.lower()
        ac = ACODEC_MAP.get(ac_key, acodec) if ac_key != 'none' else None
    else:
        ac = FORMAT_DEFAULTS.get(fmt, ('libx264', 'aac'))[1]

    cmd += ['-c:v', vc]

    # Target size (two-pass bitrate)
    if target_size_mb:
        audio_kbps = 128 if ac else 0
        video_kbps = _calc_bitrate_for_size(target_size_mb, duration, audio_kbps)
        _log(f"Target: {target_size_mb}MB -> video {video_kbps}kbps + audio {audio_kbps}kbps")
        cmd += ['-b:v', f'{video_kbps}k', '-maxrate', f'{int(video_kbps * 1.5)}k',
                '-bufsize', f'{video_kbps * 2}k']
    elif vc not in ('copy',) and quality is not None:
        if vc in ('libx264', 'libx265'):
            cmd += ['-crf', str(quality), '-preset', 'medium']
        elif vc == 'libvpx-vp9':
            cmd += ['-crf', str(quality), '-b:v', '0']
        elif vc == 'libsvtav1':
            cmd += ['-crf', str(quality)]

    # Audio codec
    if ac is None:
        cmd += ['-an']
    else:
        cmd += ['-c:a', ac]
        if ac == 'aac':
            cmd += ['-b:a', '192k']
        elif ac == 'libopus':
            cmd += ['-b:a', '128k']
        elif ac == 'libmp3lame':
            cmd += ['-b:a', '192k']

    # FPS
    if fps:
        cmd += ['-r', str(fps)]

    # Faststart
    if faststart and fmt == 'mp4':
        cmd += ['-movflags', '+faststart']

    # Pixel format for max compatibility
    if vc in ('libx264',) and not hdr_to_sdr:
        cmd += ['-pix_fmt', 'yuv420p']

    # Extra args
    if extra_args:
        cmd += extra_args

    cmd += ['-y', out_path]

    # ── Execute ──────────────────────────────────────────────────────

    if dry_run:
        _log(f"Command: {' '.join(cmd)}")
        return out_path

    _log(f"Converting: {src.name} -> {Path(out_path).name}")
    if target_res:
        _log(f"Resolution: {src_w}x{src_h} -> {target_res[0]}x{target_res[1]}")

    result = _run(cmd)

    # Cleanup temp files
    if transforms_file and os.path.exists(transforms_file):
        os.unlink(transforms_file)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-500:]}")

    out_size = os.path.getsize(out_path)
    src_size = os.path.getsize(filepath)
    _log(f"Done: {_human_size(src_size)} -> {_human_size(out_size)} ({Path(out_path).name})")
    return out_path


# ── Concat ────────────────────────────────────────────────────────────

def concat_videos(files, output=None, copy=True):
    """Concatenate multiple videos into one."""
    if output is None:
        output = str(Path(files[0]).with_stem(Path(files[0]).stem + '_joined').with_suffix('.mp4'))

    # Create concat file
    concat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    for f in files:
        concat_file.write(f"file '{os.path.abspath(f)}'\n")
    concat_file.close()

    cmd = ['ffmpeg', '-nostdin', '-f', 'concat', '-safe', '0', '-i', concat_file.name]
    if copy:
        cmd += ['-c', 'copy']
    else:
        cmd += ['-c:v', 'libx264', '-crf', '18', '-preset', 'medium',
                '-c:a', 'aac', '-b:a', '192k']
    cmd += ['-y', output]

    _log(f"Concatenating {len(files)} videos...")
    result = _run(cmd)
    os.unlink(concat_file.name)

    if result.returncode != 0:
        raise RuntimeError(f"Concat failed:\n{result.stderr[-500:]}")
    _log(f"Done: {Path(output).name} ({_human_size(os.path.getsize(output))})")
    return output


# ── Batch ─────────────────────────────────────────────────────────────

def convert_folder(folder_path, **kwargs):
    """Convert all video files in a folder."""
    folder = Path(folder_path)
    results = []
    files = sorted([
        f for f in folder.iterdir()
        if f.suffix.lower() in VIDEO_EXTENSIONS and f.is_file()
    ])
    if not files:
        _log("No video files found.")
        return results
    _log(f"Found {len(files)} video(s) in {folder.name}\n")
    for f in files:
        try:
            out = convert(str(f), **kwargs)
            results.append(out)
        except Exception as e:
            _log(f"Error on {f.name}: {e}")
    return results


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Video conversion & processing tool.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Input
    parser.add_argument('input', help='Input video file or folder')

    # Format & codec
    g = parser.add_argument_group('Format & Codec')
    g.add_argument('-f', '--format', dest='fmt', help='Output format (mp4, webm, mkv, avi, mov, gif)')
    g.add_argument('-vc', '--vcodec', help='Video codec (h264, h265, vp9, av1, prores, copy)')
    g.add_argument('-ac', '--acodec', help='Audio codec (aac, opus, mp3, flac, copy, none)')
    g.add_argument('-q', '--quality', type=int, default=18, help='Quality 0-51, lower=better (default: 18)')
    g.add_argument('-r', '--resolution', help='Resolution: 360/480/720/1080/1440/4k/WxH/N%%')
    g.add_argument('-fps', '--fps', type=float, help='Output framerate')
    g.add_argument('--copy', action='store_true', help='Remux only (no re-encode)')

    # Trim & speed
    g = parser.add_argument_group('Trim & Speed')
    g.add_argument('--trim', help='Trim: START-END (e.g. 0:30-1:45 or 10-30)')
    g.add_argument('--speed', type=float, help='Speed multiplier (0.25-4.0)')
    g.add_argument('--reverse', action='store_true', help='Reverse video')
    g.add_argument('--loop', type=int, help='Loop video N times')

    # Visual effects
    g = parser.add_argument_group('Visual Effects')
    g.add_argument('--stabilize', action='store_true', help='Stabilize shaky video (two-pass)')
    g.add_argument('--denoise', action='store_true', help='Remove video noise')
    g.add_argument('--sharpen', action='store_true', help='Sharpen video')
    g.add_argument('--fade', type=float, help='Fade in/out duration (seconds)')
    g.add_argument('--rotate', help='Rotate: 90, 180, 270, or degrees')
    g.add_argument('--hflip', action='store_true', help='Horizontal flip')
    g.add_argument('--vflip', action='store_true', help='Vertical flip')
    g.add_argument('--crop', help='Crop: W:H:X:Y or aspect ratio like 16:9')
    g.add_argument('--autocrop', action='store_true', help='Auto-remove black bars')
    g.add_argument('--lut', help='Apply color LUT (.cube file)')

    # Color
    g = parser.add_argument_group('Color & Brightness')
    g.add_argument('--brightness', type=float, help='Brightness (-1.0 to 1.0)')
    g.add_argument('--contrast', type=float, help='Contrast (0.0 to 2.0)')
    g.add_argument('--saturation', type=float, help='Saturation (0.0 to 3.0)')
    g.add_argument('--gamma', type=float, help='Gamma (0.1 to 10.0)')
    g.add_argument('--hdr-to-sdr', action='store_true', help='Tonemap HDR to SDR')

    # Audio
    g = parser.add_argument_group('Audio')
    g.add_argument('--no-audio', action='store_true', help='Strip audio track')
    g.add_argument('--normalize', action='store_true', help='Normalize audio (EBU R128)')
    g.add_argument('--volume', type=float, help='Volume multiplier (e.g. 1.5)')
    g.add_argument('--extract-audio', action='store_true', help='Extract audio only')
    g.add_argument('--audio-fade', type=float, help='Audio fade in/out (seconds)')

    # Overlay
    g = parser.add_argument_group('Overlay & Watermark')
    g.add_argument('--watermark', help='Watermark image (path:position:opacity, e.g. logo.png:br:0.5)')
    g.add_argument('--text', help='Burn text overlay')
    g.add_argument('--text-pos', default='bc', help='Text position: tl/tc/tr/bl/bc/br/c (default: bc)')
    g.add_argument('--subs', help='Burn in subtitles (.srt/.ass file)')

    # Thumbnails
    g = parser.add_argument_group('Thumbnails & Previews')
    g.add_argument('--thumbnail', type=float, nargs='?', const=-1, help='Extract frame at N seconds')
    g.add_argument('--contact-sheet', help='Create thumbnail grid (e.g. 4x4)')
    g.add_argument('--gif-preview', help='Create GIF preview (e.g. 3-8 for seconds 3 to 8)')

    # Presets
    g = parser.add_argument_group('Platform Presets')
    g.add_argument('--preset', choices=list(PLATFORM_PRESETS.keys()),
                   help='Platform preset: ' + ', '.join(PLATFORM_PRESETS.keys()))

    # Advanced
    g = parser.add_argument_group('Advanced')
    g.add_argument('--target-size', type=float, help='Target file size in MB')
    g.add_argument('--faststart', action='store_true', help='Optimize for web streaming')
    g.add_argument('--concat', nargs='+', help='Concatenate with additional files')
    g.add_argument('--dry-run', action='store_true', help='Show ffmpeg command without running')
    g.add_argument('--s3', action='store_true', help='Upload result to S3')
    g.add_argument('--info', action='store_true', help='Show video info and exit')
    g.add_argument('-o', '--output', help='Custom output path')

    args = parser.parse_args()
    path = args.input

    if not os.path.exists(path):
        _log(f"Not found: {path}")
        sys.exit(1)

    # Info mode
    if args.info:
        if os.path.isdir(path):
            for f in sorted(Path(path).iterdir()):
                if f.suffix.lower() in VIDEO_EXTENSIONS:
                    print_info(str(f))
        else:
            print_info(path)
        return

    # Thumbnail mode
    if args.thumbnail is not None:
        t = None if args.thumbnail == -1 else args.thumbnail
        out = extract_thumbnail(path, time_sec=t, output=args.output)
        print(out)
        return

    # Contact sheet mode
    if args.contact_sheet:
        out = create_contact_sheet(path, grid=args.contact_sheet, output=args.output)
        print(out)
        return

    # GIF preview mode
    if args.gif_preview:
        out = create_gif_preview(path, time_range=args.gif_preview, output=args.output)
        print(out)
        return

    # Concat mode
    if args.concat:
        all_files = [path] + args.concat
        out = concat_videos(all_files, output=args.output, copy=args.copy)
        results = [out]
    else:
        # Apply preset
        preset_kwargs = {}
        if args.preset:
            preset_kwargs = dict(PLATFORM_PRESETS[args.preset])
            # Extract special preset keys
            preset_extra = preset_kwargs.pop('extra_args', None)
            preset_target = preset_kwargs.pop('target_size_mb', None)
            preset_max_res = preset_kwargs.pop('max_res', None)
            preset_crop = preset_kwargs.pop('crop_aspect', None)
            if preset_extra:
                preset_kwargs['extra_args'] = preset_extra
            if preset_target:
                preset_kwargs['target_size_mb'] = preset_target
            if preset_max_res:
                preset_kwargs['max_res'] = preset_max_res
            if preset_crop:
                preset_kwargs['crop_aspect'] = preset_crop

        # Build kwargs — CLI args override preset
        kwargs = {**preset_kwargs}  # preset as base
        # Override with CLI args where explicitly provided
        cli_map = {
            'fmt': args.fmt, 'resolution': args.resolution, 'vcodec': args.vcodec,
            'acodec': args.acodec, 'quality': args.quality, 'fps': args.fps,
            'no_audio': args.no_audio, 'output': args.output,
            'trim': args.trim, 'speed': args.speed, 'reverse': args.reverse,
            'stabilize': args.stabilize, 'denoise': args.denoise, 'sharpen': args.sharpen,
            'fade': args.fade, 'rotate': args.rotate, 'hflip': args.hflip, 'vflip': args.vflip,
            'crop': args.crop, 'autocrop': args.autocrop, 'lut': args.lut,
            'brightness': args.brightness, 'contrast': args.contrast,
            'saturation': args.saturation, 'gamma': args.gamma,
            'hdr_to_sdr': args.hdr_to_sdr,
            'normalize': args.normalize, 'volume': args.volume,
            'extract_audio': args.extract_audio, 'audio_fade': args.audio_fade,
            'watermark': args.watermark, 'text': args.text, 'text_pos': args.text_pos,
            'subs': args.subs,
            'copy': args.copy, 'dry_run': args.dry_run, 'loop': args.loop,
        }
        if args.target_size:
            cli_map['target_size_mb'] = args.target_size
        if args.faststart:
            cli_map['faststart'] = True

        for k, v in cli_map.items():
            if v is not None and v is not False:
                kwargs[k] = v
            elif k not in kwargs:
                kwargs[k] = v

        if os.path.isdir(path):
            results = convert_folder(path, **kwargs)
        else:
            out = convert(path, **kwargs)
            results = [out]

    if not results:
        sys.exit(1)

    # Upload to S3
    if args.s3:
        try:
            utils_dir = Path(__file__).resolve().parent.parent / 'utils'
            sys.path.insert(0, str(utils_dir))
            from upload_to_url import upload
            _log("")
            for r in results:
                url = upload(r)
                print(url)
        except ImportError:
            _log("upload_to_url.py not found — skipping S3 upload")
    else:
        for r in results:
            print(r)


if __name__ == '__main__':
    main()
