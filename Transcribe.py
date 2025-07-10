import argparse
import math
import os
import time
import warnings
import torch
import whisper
from tqdm import tqdm

# Process the audio in fixed‑length chunks so we can give the progress bar a
# meaningful total. 30 seconds strikes a good balance between speed and context.
SEGMENT_SEC = 30

def transcribe_file(mp3_path: str, model_name: str) -> None:
    """Transcribe a single .mp3 file with Whisper and save <basename>_transcript.txt."""
    if not mp3_path.lower().endswith(".mp3"):
        raise ValueError("Please provide an .mp3 file")

    out_path = f"{os.path.splitext(mp3_path)[0]}_transcript.txt"
    if os.path.exists(out_path):
        print(f"✓ Transcript already exists → {out_path}")
        return

    # Select Metal (MPS) if available, otherwise CPU.
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Using device: {device}")

    # Suppress “FP16 not supported on CPU” warning noise.
    warnings.filterwarnings("ignore", category=UserWarning)

    model = whisper.load_model(model_name).to(device)

    # Load the audio once so we know its duration and can figure out how many
    # chunks we’ll have to process.
    audio = whisper.load_audio(mp3_path)
    sample_rate = whisper.audio.SAMPLE_RATE
    total_sec = len(audio) / sample_rate
    total_segments = math.ceil(total_sec / SEGMENT_SEC)

    start = time.time()
    transcripts: list[str] = []

    # Nicely‑formatted tqdm bar that mirrors the style you asked for:
    # Transcribing <file>.txt: 100%|████…| 2/2 [00:00<00:00, 6.47tokens/s]
    with tqdm(
        total=total_segments,
        desc=f"Transcribing {os.path.basename(mp3_path)}",
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        unit="tokens",  # so the speed shows “tokens/s” like in your example
    ) as pbar:
        for i in range(total_segments):
            seg_start = int(i * SEGMENT_SEC * sample_rate)
            seg_end = int(min((i + 1) * SEGMENT_SEC * sample_rate, len(audio)))
            seg_audio = audio[seg_start:seg_end]

            # Whisper accepts a NumPy array directly, so no need to write temp files.
            seg_text = model.transcribe(seg_audio, fp16=False, verbose=False)["text"].strip()
            transcripts.append(seg_text)

            pbar.update(1)

    text = "\n".join(transcripts)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Saved → {out_path}  ({time.time() - start:.1f}s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Whisper MP3‑to‑TXT (Apple MPS)")
    parser.add_argument("file", help="Path to .mp3 file")
    parser.add_argument("--model", default="medium.en", help="Whisper model name (default: medium.en)")
    args = parser.parse_args()

    transcribe_file(args.file, args.model)


if __name__ == "__main__":
    main()
