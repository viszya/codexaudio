import argparse
import math
import os
import time
import warnings
import torch
import whisper
from tqdm import tqdm
import logging
import sys

# Process the audio in fixed-length chunks
SEGMENT_SEC = 30

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)

def transcribe_file(mp3_path: str, model_name: str) -> None:
    """Transcribe a single .mp3 file with Whisper and save <basename>_transcript.txt."""
    logger.info(f"Transcribing {os.path.basename(mp3_path)}")
    if not mp3_path.lower().endswith(".mp3"):
        raise ValueError("Please provide an .mp3 file")

    out_path = f"{os.path.splitext(mp3_path)[0]}_transcript.txt"
    if os.path.exists(out_path):
        logger.info(f"Transcript already exists: {out_path}")
        return

    device = "cpu"
    model_dir = os.getenv("WHISPER_MODEL_DIR", "/app/models/whisper")

    warnings.filterwarnings("ignore", category=UserWarning)

    logger.info(f"Loading model: {model_name}")
    try:
        model = whisper.load_model(model_name, download_root=model_dir).to(device)
    except Exception as e:
        logger.error(f"Failed to load model {model_name}: {e}")
        raise

    logger.info(f"Loading audio: {mp3_path}")
    try:
        audio = whisper.load_audio(mp3_path)
    except Exception as e:
        logger.error(f"Failed to load audio {mp3_path}: {e}")
        raise

    sample_rate = whisper.audio.SAMPLE_RATE
    total_sec = len(audio) / sample_rate
    total_segments = math.ceil(total_sec / SEGMENT_SEC)

    start = time.time()
    transcripts: list[str] = []

    with tqdm(
        total=total_segments,
        desc=f"Transcribing {os.path.basename(mp3_path)}",
        bar_format="{l_bar}{bar}|50 {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        unit="tokens",
    ) as pbar:
        for i in range(total_segments):
            seg_start = int(i * SEGMENT_SEC * sample_rate)
            seg_end = int(min((i + 1) * SEGMENT_SEC * sample_rate, len(audio)))
            seg_audio = audio[seg_start:seg_end]
            result = model.transcribe(seg_audio, fp16=False, verbose=False)
            seg_text = result["text"].strip()
            transcripts.append(seg_text)
            pbar.update(1)

    text = "\n".join(transcripts)

    logger.info(f"Saving transcript to {out_path}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    elapsed = time.time() - start
    logger.info(f"Saved transcript to {out_path} (took {elapsed:.1f}s)")

def main() -> None:
    parser = argparse.ArgumentParser(description="Whisper MP3-to-TXT")
    parser.add_argument("file", help="Path to .mp3 file")
    parser.add_argument("--model", default="medium.en", help="Whisper model name (default: medium.en)")
    args = parser.parse_args()

    try:
        transcribe_file(args.file, args.model)
    except Exception as e:
        logger.error(f"Failed to transcribe file: {str(e)}")
        raise

if __name__ == "__main__":
    main()