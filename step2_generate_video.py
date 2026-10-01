"""Step 2 - turn the voice-over script into a 1080x1920 Instagram Reel.

Run on its own:   python step2_generate_video.py
Needs:            output/<name>_script.txt (from step 1) and pictures in inputs/images
Result:           output/<name>_reel.mp4  (and output/<name>_voice.mp3)

Pipeline: edge-tts voice-over -> word timings -> Ken Burns clips per image, cut on the
pauses of the narration -> centred bold subtitles -> MoviePy export (H.264 + AAC).
"""
from __future__ import annotations

import argparse
import asyncio
import math
import os
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from config import (
    FONTS_DIR,
    IMAGES_DIR,
    OUTPUT_DIR,
    ReelsError,
    check_python,
    ensure_folders,
    load_env,
    newest_first,
    setup_console,
    show,
)

WIDTH, HEIGHT = 1080, 1920
DEFAULT_VOICE = "tr-TR-AhmetNeural"  # deep documentary voice; tr-TR-EmelNeural is the female option
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

MAX_SOURCE_SIDE = 3200  # larger scans are shrunk on load; plenty for a 1080-px wide video
MAX_SECONDS_PER_IMAGE = 8.0  # fewer pictures than this => pictures are reused so nothing lingers
CROSSFADE = 0.5  # seconds of dissolve between two images
TAIL = 0.5  # seconds of picture after the last spoken word
PAN_SPEED = 40.0  # pixels per second of sideways drift (slow on purpose)
ZOOM_PER_SECOND = 0.02  # 2 % zoom per second, capped below
MAX_ZOOM = 0.16
BLUR_CANVAS_SCALE = 1.6  # "blur" fit works on a canvas this many times larger than the frame
AUTO_BLUR_ASPECT = 0.94  # "auto" fit: images wider than this (width/height) get a blurred background

SUBTITLE_FONT_SIZE = 104
SUBTITLE_STROKE = 9
SUBTITLE_MAX_WIDTH = 940
SUBTITLE_POP_SECONDS = 0.12

SENTENCE_END = (".", "!", "?", "…")
CLAUSE_END = (",", ";", ":", "—", "–")

# (zoom direction, sideways drift, vertical drift) - cycled over the images
MOTION_PRESETS = [("in", +1, 0), ("out", -1, 0), ("in", -1, +1), ("out", +1, -1)]


# --------------------------------------------------------------------------- text helpers
def tr_upper(text: str) -> str:
    """Upper-case with Turkish rules (i -> İ, ı -> I) so subtitles are spelled correctly."""
    return text.replace("i", "İ").replace("ı", "I").upper()


def clean_for_speech(text: str) -> str:
    return " ".join(text.split())


def _norm(token: str) -> str:
    return re.sub(r"\W", "", token).casefold()


# --------------------------------------------------------------------------- voice-over
@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Boundary:
    text: str
    start: float
    end: float


async def _tts_once(text: str, audio_path: Path, voice: str, rate: str, pitch: str, boundary: str) -> list[Boundary]:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary=boundary)
    events: list[Boundary] = []
    with open(audio_path, "wb") as handle:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                handle.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                # edge-tts reports times in units of 100 nanoseconds
                start = chunk["offset"] / 1e7
                events.append(Boundary(chunk["text"], start, start + chunk["duration"] / 1e7))
    if audio_path.stat().st_size == 0:
        raise RuntimeError("the service returned no audio")
    return events


def _run_tts(text: str, audio_path: Path, voice: str, rate: str, pitch: str, boundary: str) -> list[Boundary]:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            return asyncio.run(_tts_once(text, audio_path, voice, rate, pitch, boundary))
        except Exception as exc:  # network hiccups are common; try a few times
            last_error = exc
            if attempt < 3:
                print(f"  Voice service did not answer ({exc}); retrying...")
                time.sleep(2 * attempt)
    raise ReelsError(
        f"Could not create the voice-over with Edge-TTS ({last_error}).\n"
        f"  Check your internet connection and that the voice name '{voice}' is correct."
    )


def spread(tokens: list[str], start: float, end: float) -> list[Word]:
    """Share the time between start and end among tokens, longer words (and pauses) taking longer."""
    if not tokens:
        return []
    weights = []
    for token in tokens:
        weight = len(token) + 2
        if token.endswith(SENTENCE_END):
            weight += 6
        elif token.endswith(CLAUSE_END):
            weight += 3
        weights.append(weight)
    span = max(end - start, 0.01)
    unit = span / sum(weights)
    words, cursor = [], start
    for token, weight in zip(tokens, weights):
        words.append(Word(token, cursor, cursor + weight * unit))
        cursor += weight * unit
    return words


def synthesize_voice(text: str, audio_path: Path, voice: str, rate: str, pitch: str) -> tuple[list[Boundary], str]:
    """Create the mp3 and return the timing events plus their kind ('WordBoundary'/'SentenceBoundary'/'none')."""
    for boundary in ("WordBoundary", "SentenceBoundary"):
        events = _run_tts(text, audio_path, voice, rate, pitch, boundary)
        if events:
            return events, boundary
    return [], "none"


def build_words(events: list[Boundary], kind: str, text: str, total: float) -> list[Word]:
    """Turn the service's timing events into one timed Word per subtitle token."""
    tokens = text.split()
    if kind == "WordBoundary":
        timed = [Word(e.text, e.start, min(e.end, total)) for e in events]
        # The service drops punctuation; restore it from the script when the words line up 1:1.
        if len(timed) == len(tokens) and all(_norm(w.text) == _norm(t) for w, t in zip(timed, tokens)):
            for word, token in zip(timed, tokens):
                word.text = token
        return timed
    if kind == "SentenceBoundary":
        words: list[Word] = []
        for event in events:
            words.extend(spread(event.text.split(), event.start, min(event.end, total)))
        return words
    return spread(tokens, 0.0, total)


# --------------------------------------------------------------------------- subtitles
@dataclass
class Chunk:
    text: str
    start: float
    end: float
    last_word_end: float
    ends_clause: bool


def build_chunks(words: list[Word], total: float, max_words: int, max_chars: int = 24) -> list[Chunk]:
    """Group words into short phrases that appear exactly while they are spoken."""
    groups: list[list[Word]] = []
    current: list[Word] = []
    for word in words:
        too_long = len(" ".join(w.text for w in current + [word])) > max_chars
        if current and (len(current) >= max_words or too_long):
            groups.append(current)
            current = []
        current.append(word)
        if word.text.endswith(SENTENCE_END) or (word.text.endswith(CLAUSE_END) and len(current) >= 2):
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    chunks: list[Chunk] = []
    for i, group in enumerate(groups):
        last = group[-1]
        next_start = groups[i + 1][0].start if i + 1 < len(groups) else total + TAIL
        start = group[0].start
        end = max(min(next_start, last.end + 0.25), start + 0.15)  # linger briefly, never overlap
        chunks.append(
            Chunk(
                text=" ".join(w.text for w in group),
                start=start,
                end=end,
                last_word_end=last.end,
                ends_clause=last.text.endswith(SENTENCE_END + CLAUSE_END),
            )
        )
    return chunks


FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\calibrib.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]


def find_font() -> str | None:
    """Pick a bold font that has Turkish letters: SUBTITLE_FONT, then fonts/, then the system."""
    configured = (os.getenv("SUBTITLE_FONT") or "").strip()
    if configured:
        if Path(configured).is_file():
            return configured
        print(f"  Warning: SUBTITLE_FONT '{configured}' was not found; looking for another font.")
    if FONTS_DIR.is_dir():
        for path in sorted(FONTS_DIR.iterdir()):
            if path.suffix.lower() in {".ttf", ".otf"}:
                return str(path)
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def _load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont:
    if font_path:
        return ImageFont.truetype(font_path, size)
    return ImageFont.load_default(size)


def render_subtitle(text: str, font_path: str | None, uppercase: bool = True) -> np.ndarray:
    """Draw bold white text with a black outline on a transparent canvas (RGBA array)."""
    text = tr_upper(text) if uppercase else text
    size = SUBTITLE_FONT_SIZE
    while True:
        font = _load_font(font_path, size)
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if line and font.getlength(trial) > SUBTITLE_MAX_WIDTH:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
        widest = max(font.getlength(l) for l in lines)
        if widest <= SUBTITLE_MAX_WIDTH or size <= 48:
            break
        size = int(size * 0.92)  # a very long word: shrink the font until it fits

    stroke = max(4, round(SUBTITLE_STROKE * size / SUBTITLE_FONT_SIZE))
    ascent, descent = font.getmetrics()
    line_height = ascent + descent + round(size * 0.08)
    pad = stroke + 8
    canvas_w = int(math.ceil(widest)) + 2 * pad
    canvas_h = line_height * len(lines) + 2 * pad
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for i, line in enumerate(lines):
        draw.text(
            (canvas_w / 2, pad + i * line_height),
            line,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=stroke,
            stroke_fill=(0, 0, 0, 255),
            anchor="ma",
        )
    return np.asarray(canvas)


# --------------------------------------------------------------------------- images + Ken Burns
def natural_key(path: Path) -> list:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def list_images(folder: Path) -> list[Path]:
    found, skipped = [], []
    for path in sorted(folder.iterdir(), key=natural_key):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            found.append(path)
        else:
            skipped.append(path.name)
    if skipped:
        print(f"  Skipping files that are not supported pictures: {', '.join(skipped)}")
    valid = []
    for path in found:
        try:
            with Image.open(path) as probe:
                probe.verify()
            valid.append(path)
        except Exception as exc:
            print(f"  Skipping '{path.name}': it cannot be opened as a picture ({exc}).")
    if not valid:
        raise ReelsError(
            f"No usable pictures found in '{show(folder)}'. Copy .jpg, .png or .webp files there "
            "(they are used in alphabetical order, so name them 01_..., 02_... to control the order)."
        )
    return valid


def load_image(path: Path) -> Image.Image:
    Image.MAX_IMAGE_PIXELS = None  # museum scans can be huge; they come from the user's own disk
    with Image.open(path) as opened:
        opened.draft("RGB", (MAX_SOURCE_SIDE, MAX_SOURCE_SIDE))  # fast, low-memory JPEG decoding
        image = ImageOps.exif_transpose(opened)
        if image.mode in ("RGBA", "LA", "P"):
            rgba = image.convert("RGBA")
            image = Image.new("RGB", rgba.size, (0, 0, 0))
            image.paste(rgba, mask=rgba.getchannel("A"))
        else:
            image = image.convert("RGB")
    image.thumbnail((MAX_SOURCE_SIDE, MAX_SOURCE_SIDE), Image.LANCZOS)
    return image


@lru_cache(maxsize=3)
def prepare_source(path: str, fit: str) -> tuple[Image.Image, str]:
    """Return the picture Ken Burns will move over, and the fit mode actually used."""
    image = load_image(Path(path))
    mode = fit
    if mode == "auto":
        mode = "blur" if image.width / image.height > AUTO_BLUR_ASPECT else "cover"
    if mode == "cover":
        return image, mode

    # "blur": the whole picture, centred on a darkened, blurred copy of itself (9:16 canvas)
    canvas_w, canvas_h = round(WIDTH * BLUR_CANVAS_SCALE), round(HEIGHT * BLUR_CANVAS_SCALE)
    small = ImageOps.fit(image, (canvas_w // 6, canvas_h // 6), Image.BILINEAR)
    background = small.filter(ImageFilter.GaussianBlur(6)).resize((canvas_w, canvas_h), Image.BICUBIC)
    background = ImageEnhance.Brightness(background).enhance(0.55)
    scale = min(canvas_w / image.width, canvas_h / image.height)
    foreground = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    background.paste(foreground, ((canvas_w - foreground.width) // 2, (canvas_h - foreground.height) // 2))
    return background, mode


def make_ken_burns_clip(path: Path, index: int, duration: float, fit: str):
    """A silent clip of `duration` seconds that slowly zooms and drifts over the picture."""
    from moviepy import VideoClip

    zoom_dir, pan_x, pan_y = MOTION_PRESETS[index % len(MOTION_PRESETS)]
    key = str(path)

    def frame(t: float) -> np.ndarray:
        source, mode = prepare_source(key, fit)
        src_w, src_h = source.size
        amount = min(MAX_ZOOM, ZOOM_PER_SECOND * duration)
        if mode == "blur":
            amount = min(amount, 0.07)  # keep the framed picture mostly intact
        z_start, z_end = (1.0, 1.0 + amount) if zoom_dir == "in" else (1.0 + amount, 1.0)

        base = max(WIDTH / src_w, HEIGHT / src_h)  # scale at which the picture just covers the frame
        z_mid = (z_start + z_end) / 2
        slack_x = max(src_w * base * z_mid - WIDTH, 0.0)
        slack_y = max(src_h * base * z_mid - HEIGHT, 0.0)
        # how much of the available room we drift through (limited by PAN_SPEED => always slow)
        span_x = min(1.0, PAN_SPEED * duration / slack_x) if slack_x > 1 and mode == "cover" else 0.0
        span_y = min(1.0, 0.6 * PAN_SPEED * duration / slack_y) if slack_y > 1 and mode == "cover" else 0.0

        progress = min(max(t / duration, 0.0), 1.0)
        eased = progress * progress * (3 - 2 * progress)  # ease in/out
        zoom = z_start + (z_end - z_start) * eased
        view_w, view_h = WIDTH / (base * zoom), HEIGHT / (base * zoom)
        u = 0.5 + pan_x * span_x * (eased - 0.5)
        v = 0.5 + pan_y * span_y * (eased - 0.5)
        left = u * (src_w - view_w)
        top = v * (src_h - view_h)
        box = (left, top, min(left + view_w, src_w), min(top + view_h, src_h))
        # a fractional crop box keeps the motion perfectly smooth (no pixel jitter)
        return np.asarray(source.resize((WIDTH, HEIGHT), Image.BICUBIC, box=box))

    return VideoClip(frame, duration=duration)


# --------------------------------------------------------------------------- timeline
def plan_cuts(slots: int, total: float, chunks: list[Chunk]) -> list[float]:
    """Boundaries between picture slots: evenly spread, nudged onto nearby pauses in the narration."""
    segment = total / slots
    pauses = [
        (chunks[i].last_word_end + chunks[i + 1].start) / 2
        for i in range(len(chunks) - 1)
        if chunks[i].ends_clause
    ]
    min_segment = min(1.5, 0.5 * segment)
    cuts, previous = [], 0.0
    for k in range(1, slots):
        ideal = segment * k
        near = [p for p in pauses if abs(p - ideal) <= 0.3 * segment]
        cut = min(near, key=lambda p: abs(p - ideal)) if near else ideal
        cut = max(cut, previous + min_segment)
        cut = min(cut, total - min_segment * (slots - k))
        cuts.append(cut)
        previous = cut
    return cuts


def make_subtitle_clip(chunk: Chunk, font_path: str | None, uppercase: bool):
    from moviepy import ImageClip

    image = render_subtitle(chunk.text, font_path, uppercase)
    clip = ImageClip(image).with_start(chunk.start).with_duration(chunk.end - chunk.start)
    # quick "pop": the phrase grows from 85 % to full size as it appears
    clip = clip.resized(lambda t: 0.85 + 0.15 * min(1.0, t / SUBTITLE_POP_SECONDS))
    return clip.with_position(("center", "center"))


# --------------------------------------------------------------------------- public entry point
def find_script(explicit: Path | None) -> Path:
    if explicit is not None:
        path = explicit if explicit.is_absolute() else Path.cwd() / explicit
        if not path.is_file():
            raise ReelsError(f"The script file '{explicit}' does not exist.")
        return path
    scripts = newest_first(list(OUTPUT_DIR.glob("*_script.txt")))
    if not scripts:
        raise ReelsError(
            f"No script found in '{show(OUTPUT_DIR)}'. Run step 1 first (python main.py --only script), "
            "or point to a text file with --script."
        )
    return scripts[0]


def generate_video(
    script_path: Path | None = None,
    *,
    voice: str | None = None,
    rate: int | None = None,
    pitch: int | None = None,
    fit: str = "auto",
    fps: int = 30,
    words_per_chunk: int = 3,
    uppercase: bool = True,
    output_path: Path | None = None,
) -> Path:
    """Run step 2 and return the path of the finished .mp4."""
    ensure_folders()
    load_env()
    from moviepy import AudioFileClip, CompositeVideoClip, vfx

    voice = voice or os.getenv("TTS_VOICE", "").strip() or DEFAULT_VOICE
    rate = rate if rate is not None else int(os.getenv("TTS_RATE", "0") or 0)
    pitch = pitch if pitch is not None else int(os.getenv("TTS_PITCH", "0") or 0)

    script_file = find_script(script_path)
    text = clean_for_speech(script_file.read_text(encoding="utf-8-sig"))
    if not text:
        raise ReelsError(f"The script file '{script_file.name}' is empty.")
    print(f"  Script: {show(script_file)} ({len(text.split())} words)")

    images = list_images(IMAGES_DIR)
    print(f"  Pictures: {len(images)} found in {show(IMAGES_DIR)}")

    stem = script_file.stem.removesuffix("_script")
    audio_path = OUTPUT_DIR / f"{stem}_voice.mp3"
    video_path = output_path or OUTPUT_DIR / f"{stem}_reel.mp4"

    # 1) voice-over ----------------------------------------------------------------------
    print(f"  Creating the voice-over with Edge-TTS ({voice})...")
    events, kind = synthesize_voice(text, audio_path, voice, f"{rate:+d}%", f"{pitch:+d}Hz")
    audio = AudioFileClip(str(audio_path))
    total = float(audio.duration)
    words = build_words(events, kind, text, total)
    if kind == "none":
        print("  (The service sent no word timings; subtitle timing is estimated from the audio length.)")
    elif kind == "SentenceBoundary":
        print("  (Sentence timings received; word timing inside each sentence is estimated.)")
    print(f"  Voice-over length: {total:.1f} seconds")

    # 2) subtitles + timeline --------------------------------------------------------------
    chunks = build_chunks(words, total, words_per_chunk)
    slots = max(len(images), math.ceil(total / MAX_SECONDS_PER_IMAGE))
    if slots > len(images):
        print(f"  Only {len(images)} picture(s) for {total:.0f} s: pictures will repeat so none stays on screen too long.")
    elif total / slots < 2.0:
        print(f"  Note: {len(images)} pictures in {total:.0f} s means about {total / slots:.1f} s per picture (quite fast).")
    cuts = plan_cuts(slots, total, chunks)
    boundaries = [0.0] + cuts + [total + TAIL]
    fade = min(CROSSFADE, 0.4 * (total / slots))

    font_path = find_font()
    if font_path is None:
        print("  Warning: no bold font found; using a basic font. See README ('fonts' folder) to add one.")
    else:
        print(f"  Subtitle font: {Path(font_path).name}")

    # 3) picture clips with Ken Burns, dissolving into each other -----------------------------
    layers = []
    for i in range(slots):
        start = boundaries[i] - (fade / 2 if i > 0 else 0.0)
        end = boundaries[i + 1] + (fade / 2 if i < slots - 1 else 0.0)
        clip = make_ken_burns_clip(images[i % len(images)], i, end - start, fit).with_start(start)
        if i > 0:
            clip = clip.with_effects([vfx.CrossFadeIn(fade)])
        layers.append(clip)

    # 4) subtitles on top, centred ----------------------------------------------------------------
    layers.extend(make_subtitle_clip(chunk, font_path, uppercase) for chunk in chunks)

    video = CompositeVideoClip(layers, size=(WIDTH, HEIGHT)).with_duration(total + TAIL).with_audio(audio)

    # 5) export ----------------------------------------------------------------------------------
    print(f"  Rendering {WIDTH}x{HEIGHT} at {fps} fps - this can take several minutes...")
    video.write_videofile(
        str(video_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        pixel_format="yuv420p",  # required for Instagram / phones
        ffmpeg_params=["-crf", "19", "-movflags", "+faststart"],
        temp_audiofile_path=str(OUTPUT_DIR),
        threads=os.cpu_count() or 2,
    )
    video.close()
    audio.close()
    print(f"  Saved: {show(video_path)}")
    return video_path


def build_arg_parser(add_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=add_help)
    parser.add_argument("--script", type=Path, help="script .txt to turn into a video (default: newest in output/)")
    parser.add_argument("--voice", help=f"Edge-TTS voice (default: {DEFAULT_VOICE})")
    parser.add_argument("--rate", type=int, help="speaking speed change in percent, e.g. -10 = slower (default 0)")
    parser.add_argument("--pitch", type=int, help="voice pitch change in Hz, e.g. -5 = deeper (default 0)")
    parser.add_argument(
        "--fit",
        choices=["auto", "cover", "blur"],
        default="auto",
        help="auto: wide pictures keep their full frame on a blurred background, tall ones fill the screen; "
        "cover: always fill the screen (crops); blur: always show the whole picture",
    )
    parser.add_argument("--fps", type=int, default=30, help="frames per second (default 30)")
    parser.add_argument("--words", type=int, default=3, help="max words shown at once in the subtitles (default 3)")
    parser.add_argument("--no-uppercase", action="store_true", help="show subtitles in normal letter case")
    return parser


def main() -> None:
    setup_console()
    args = build_arg_parser().parse_args()
    try:
        check_python()
        generate_video(
            args.script,
            voice=args.voice,
            rate=args.rate,
            pitch=args.pitch,
            fit=args.fit,
            fps=args.fps,
            words_per_chunk=args.words,
            uppercase=not args.no_uppercase,
        )
    except ReelsError as exc:
        raise SystemExit(f"\nERROR: {exc}")


if __name__ == "__main__":
    main()
