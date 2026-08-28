# video-convert

A single-file `ffmpeg` front-end that covers the video chores you actually hit — conversion,
resizing, trimming, effects, watermarks, contact sheets and platform presets — without
memorising filter-graph syntax every time.

One script, no dependencies beyond `ffmpeg`/`ffprobe` on `PATH`.

```bash
python video_convert.py input.mov                    # MOV -> MP4
python video_convert.py input.mov -r 1080 -vc h265   # 1080p, H.265
python video_convert.py input.mov --trim 0:30-1:45   # cut a segment
python video_convert.py input.mov --preset youtube    # platform-tuned encode
python video_convert.py input.mov --dry-run          # print the ffmpeg command instead
```

## What it covers

| Area | Options |
|---|---|
| Convert | target format, video/audio codec, remux-only (`--copy`) |
| Resize | `1080` · `4k` · `1280x720` · `50%` |
| Trim & time | `--trim`, `--speed`, `--reverse`, `--loop`, `--concat` |
| Effects | stabilise, denoise, sharpen, fade, rotate, flip, crop, autocrop, `--lut file.cube` |
| Colour | brightness, contrast, saturation, gamma, `--hdr-to-sdr` |
| Audio | strip, EBU R128 normalise, volume, extract, fade |
| Overlay | image watermark (position + opacity), burnt-in text, burnt-in `.srt` subtitles |
| Stills | `--thumbnail`, `--contact-sheet 4x4`, `--gif-preview 3-8` |
| Presets | youtube · twitter · discord · instagram-reels · whatsapp · web |
| Sizing | `--target-size 25` (fit N MB), `--faststart` |
| Batch | pass a folder instead of a file |

`--info` prints a `ffprobe` summary. `--dry-run` prints the command it would run, which makes
this usable as a filter-graph reference as much as a tool.

## Install

```bash
# ffmpeg + ffprobe must be on PATH
brew install ffmpeg          # macOS
sudo apt install ffmpeg      # Debian/Ubuntu
```

`--s3` is optional: it imports a local `upload_to_url.py` if one is present and skips the
upload with a warning if not.
