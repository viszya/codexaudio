from pathlib import Path
import argparse
import torch
from transformers import AutoProcessor, Gemma3ForConditionalGeneration
import logging
from tqdm import tqdm
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)

DEFAULT_MODEL = "google/gemma-3-4b-it"
DEFAULT_PROMPT = Path("prompt.txt").read_text(encoding="utf-8") if os.path.exists("prompt.txt") else "Summarize the following transcript:\n{transcript}"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.1

# Load Hugging Face token
HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    logger.error("HF_TOKEN environment variable is not set")
    raise ValueError("HF_TOKEN environment variable is not set")

# Set cache directory
cache_dir = os.getenv("HF_HOME", "/app/models/huggingface")
logger.info(f"Using cache directory: {cache_dir}")

# Load model and processor globally
logger.info(f"Loading model: {DEFAULT_MODEL}")
try:
    MODEL = Gemma3ForConditionalGeneration.from_pretrained(
        DEFAULT_MODEL,
        torch_dtype=torch.bfloat16,
        cache_dir=cache_dir,
        token=HF_TOKEN
    ).to("cpu").eval()
    logger.info(f"Loaded model: {DEFAULT_MODEL}")
except Exception as e:
    logger.error(f"Failed to load model {DEFAULT_MODEL}: {e}")
    raise

logger.info(f"Loading processor: {DEFAULT_MODEL}")
try:
    PROCESSOR = AutoProcessor.from_pretrained(
        DEFAULT_MODEL,
        use_fast=True,
        cache_dir=cache_dir,
        token=HF_TOKEN
    )
    logger.info(f"Loaded processor: {DEFAULT_MODEL}")
except Exception as e:
    logger.error(f"Failed to load processor {DEFAULT_MODEL}: {e}")
    raise

def default_md_path(txt_path: str) -> str:
    """Convert ./foo_transcript.txt to ./foo_summary.md"""
    p = Path(txt_path)
    new_stem = p.stem.replace('_transcript', '_summary')
    return str(p.with_stem(new_stem).with_suffix('.md'))

def summarize(txt_path: str,
              model_id: str = DEFAULT_MODEL,
              prompt_template: str = DEFAULT_PROMPT,
              md_out_path: str | None = None,
              max_tokens: int = DEFAULT_MAX_TOKENS,
              temperature: float = DEFAULT_TEMPERATURE) -> str:
    """Return summary text (and write it to *md_out_path*)."""
    logger.info(f"Summarizing {os.path.basename(txt_path)}")
    transcript = Path(txt_path).read_text(encoding="utf-8")
    prompt = prompt_template.format(transcript=transcript)

    # Use global model and processor
    model = MODEL
    processor = PROCESSOR

    # Prepare input
    logger.info("Preparing input")
    messages = [
        {"role": "system", "content": [{"type": "text", "text": "You are a helpful assistant."}]},
        {"role": "user", "content": [{"type": "text", "text": prompt}]}
    ]
    inputs = processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True,
        return_dict=True, return_tensors="pt"
    ).to(model.device, dtype=torch.bfloat16)

    input_len = inputs["input_ids"].shape[-1]

    # Generate summary
    logger.info("Generating summary")
    with torch.inference_mode():
        generation = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=True if temperature > 0 else False
        )
        generation = generation[0][input_len:]

    summary = processor.decode(generation, skip_special_tokens=True).lstrip()
    out_path = md_out_path or default_md_path(txt_path)
    logger.info(f"Saving summary to {out_path}")
    Path(out_path).write_text(summary, encoding="utf-8")
    return summary

def process_in_chunks(txt_path: str, chunk_size: int = 5000) -> str:
    """Process the transcript in chunks and generate a summary."""
    logger.info(f"Processing {os.path.basename(txt_path)} in chunks")
    with open(txt_path, "r", encoding="utf-8") as file:
        transcript = file.read()

    chunks = [transcript[i:i + chunk_size] for i in range(0, len(transcript), chunk_size)]
    logger.info(f"Split into {len(chunks)} chunks")

    full_summary = ""
    with tqdm(total=len(chunks), desc="Summarizing chunks", unit="chunk") as pbar:
        for idx, chunk in enumerate(chunks):
            chunk_summary = summarize_chunk(chunk)
            full_summary += chunk_summary + "\n"
            pbar.update(1)
    
    return full_summary

def summarize_chunk(chunk: str) -> str:
    """Summarize an individual chunk."""
    logger.info("Summarizing chunk")
    prompt = DEFAULT_PROMPT.format(transcript=chunk)
    messages = [
        {"role": "system", "content": [{"type": "text", "text": "You are a helpful assistant."}]},
        {"role": "user", "content": [{"type": "text", "text": prompt}]}
    ]
    inputs = PROCESSOR.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True,
        return_dict=True, return_tensors="pt"
    ).to(MODEL.device, dtype=torch.bfloat16)

    input_len = inputs["input_ids"].shape[-1]

    with torch.inference_mode():
        generation = MODEL.generate(
            **inputs,
            max_new_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE,
            do_sample=True if DEFAULT_TEMPERATURE > 0 else False
        )
        generation = generation[0][input_len:]

    summary = PROCESSOR.decode(generation, skip_special_tokens=True).lstrip()
    return summary

def main() -> None:
    ap = argparse.ArgumentParser(description="Summarize a transcript using Gemma 3.")
    ap.add_argument("txt", help="Path to the .txt transcript")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="Hugging Face model ID")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="Prompt text or path to prompt.txt")
    ap.add_argument("--out", help="Markdown output path (default: <txt>.md)")
    ap.add_argument("--max_tokens", type=int, default=DEFAULT_MAX_TOKENS)
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    args = ap.parse_args()

    logger.info(f"Summarizing {os.path.basename(args.txt)}")
    full_summary = process_in_chunks(args.txt)
    out_path = args.out or default_md_path(args.txt)
    logger.info(f"Saving summary to {out_path}")
    Path(out_path).write_text(full_summary, encoding="utf-8")

if __name__ == "__main__":
    main()