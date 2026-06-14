#!/usr/bin/env python3
"""
Transcribe a large audio file using local OpenAI Whisper.

Usage:
    python transcribe.py <audio_file> [--model <model>] [--output <output_file>]

Models (smallest to largest, faster to slower):
    tiny, base, small, medium, large
"""

import argparse
import os
import sys
import math
import tempfile
import subprocess
from pathlib import Path


def check_dependencies():
    missing = []
    try:
        import whisper
    except ImportError:
        missing.append("openai-whisper")
    try:
        import ffmpeg  # noqa: F401
    except ImportError:
        # ffmpeg-python is optional; we use subprocess fallback
        pass
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)


def get_audio_duration(path: str) -> float:
    """Return duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def split_audio(input_path: str, chunk_seconds: int, tmp_dir: str) -> list[str]:
    """Split audio into chunks using ffmpeg. Returns list of chunk paths."""
    duration = get_audio_duration(input_path)
    num_chunks = math.ceil(duration / chunk_seconds)
    chunks = []

    for i in range(num_chunks):
        start = i * chunk_seconds
        out_path = os.path.join(tmp_dir, f"chunk_{i:04d}.wav")
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", input_path,
                "-ss", str(start),
                "-t", str(chunk_seconds),
                "-ar", "16000", "-ac", "1",
                out_path,
            ],
            check=True,
        )
        chunks.append(out_path)
        print(f"  Prepared chunk {i + 1}/{num_chunks} ({start:.0f}s – {min(start + chunk_seconds, duration):.0f}s)")

    return chunks


def transcribe_chunks(chunks: list[str], model_name: str, language: str | None = None) -> str:
    import whisper

    print(f"\nLoading Whisper model '{model_name}' ...")
    model = whisper.load_model(model_name)
    parts = []

    for i, chunk_path in enumerate(chunks):
        print(f"  Transcribing chunk {i + 1}/{len(chunks)} ...")
        result = model.transcribe(chunk_path, fp16=False, language=language)
        parts.append(result["text"].strip())

    return " ".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Transcribe a large audio file with local Whisper.")
    parser.add_argument("audio_file", help="Path to the audio file")
    parser.add_argument("--model", default="base", choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper model to use (default: base)")
    parser.add_argument("--language", default=None,
                        help="Language code to force (e.g. 'nl' for Dutch, 'en' for English). "
                             "Auto-detected if omitted.")
    parser.add_argument("--chunk-minutes", type=int, default=10,
                        help="Split audio into N-minute chunks (default: 10)")
    parser.add_argument("--output", help="Save transcript to this .md file (default: <audio_file>.md)")
    args = parser.parse_args()

    check_dependencies()

    audio_path = args.audio_file
    if not os.path.isfile(audio_path):
        print(f"Error: file not found: {audio_path}")
        sys.exit(1)

    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"Audio file: {audio_path} ({file_size_mb:.1f} MB)")

    chunk_seconds = args.chunk_minutes * 60

    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"\nSplitting into {args.chunk_minutes}-minute chunks ...")
        chunks = split_audio(audio_path, chunk_seconds, tmp_dir)

        transcript = transcribe_chunks(chunks, args.model, language=args.language)

    out_path = Path(args.output) if args.output else Path(audio_path).with_suffix(".md")

    audio_name = Path(audio_path).name
    md_content = f"# Transcript: {audio_name}\n\n{transcript}\n"
    out_path.write_text(md_content, encoding="utf-8")

    print("\n--- TRANSCRIPT ---\n")
    print(transcript)
    print(f"\nTranscript saved to: {out_path}")


if __name__ == "__main__":
    main()
