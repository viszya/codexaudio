from pathlib import Path
import argparse
from transformers import AutoProcessor, Gemma3ForConditionalGeneration
import torch
import logging
from tqdm import tqdm 
from time import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "google/gemma-3-4b-it"
DEFAULT_PROMPT = Path("prompt.txt").read_text(encoding="utf-8")
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.1

# Ensure MPS is available
if not torch.backends.mps.is_available():
    logger.error("MPS backend is not available. Falling back to CPU.")
    device = "cpu"
else:
    device = "mps"
logger.info(f"Using device: {device}")

# Load model and processor
try:
    MODEL = Gemma3ForConditionalGeneration.from_pretrained(
        DEFAULT_MODEL,
        torch_dtype=torch.bfloat16,
        device_map=None  # Explicitly manage device placement
    ).to(device).eval()
    PROCESSOR = AutoProcessor.from_pretrained(
        DEFAULT_MODEL,
        use_fast=True  # Enable fast processor to suppress warning
    )
except Exception as e:
    logger.error(f"Failed to load model {DEFAULT_MODEL}: {e}")
    raise

def default_md_path(md_path: str) -> str:
    """Convert ./foo_transcript.txt to ./foo_summary.md"""
    p = Path(md_path)
    new_stem = p.stem.replace('_transcript', '_summary')
    return str(p.with_stem(new_stem).with_suffix('.md'))

def summarize(txt_path: str,
              model_id: str = DEFAULT_MODEL,
              prompt_template: str = DEFAULT_PROMPT,
              md_out_path: str | None = None,
              max_tokens: int = DEFAULT_MAX_TOKENS,
              temperature: float = DEFAULT_TEMPERATURE) -> str:
    """Return summary text (and write it to *md_out_path*)."""
    # Load transcript
    transcript = Path(txt_path).read_text(encoding="utf-8")
    prompt = prompt_template.format(transcript=transcript)

    # Use global model and processor
    model = MODEL
    processor = PROCESSOR

    # Prepare input using chat template
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
    with torch.inference_mode():
        generation = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=True if temperature > 0 else False
        )
        generation = generation[0][input_len:]

    summary = processor.decode(generation, skip_special_tokens=True).lstrip()

    # Write to output file
    out_path = md_out_path or default_md_path(txt_path)
    Path(out_path).write_text(summary, encoding="utf-8")
    return summary

def process_in_chunks(txt_path: str, chunk_size: int = 5000) -> str:
    """Process the transcript in chunks and generate a summary."""
    with open(txt_path, "r", encoding="utf-8") as file:
        transcript = file.read()

    # Split the transcript into chunks
    chunks = [transcript[i:i + chunk_size] for i in range(0, len(transcript), chunk_size)]

    full_summary = ""
    with tqdm(total=len(chunks), desc="Processing chunks", unit="chunk", dynamic_ncols=True) as pbar:
        for idx, chunk in enumerate(chunks):
            start_time = time()  # Record start time for this chunk
            chunk_summary = summarize_chunk(chunk)
            end_time = time()  # Record end time for this chunk
            time_taken = end_time - start_time  # Calculate time taken for this chunk
            
            full_summary += chunk_summary + "\n"
            
            # Update progress bar with correct time per chunk
            pbar.set_postfix({"chunk": idx + 1, "time_per_chunk": f"{time_taken:.2f}s"})
            
            # Ensure the progress bar updates
            pbar.update(1)
    
    return full_summary

def summarize_chunk(chunk: str) -> str:
    """Summarize an individual chunk."""
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

    # Generate summary
    with torch.inference_mode():
        generation = MODEL.generate(
            **inputs,
            max_new_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE,
            do_sample=True if DEFAULT_TEMPERATURE > 0 else False
        )
        generation = generation[0][input_len:]

    return PROCESSOR.decode(generation, skip_special_tokens=True).lstrip()

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Summarize a 2-person meeting transcript using Gemma 3."
    )
    ap.add_argument("txt", help="Path to the .txt transcript")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="Hugging Face model ID")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="Path to prompt.txt")
    ap.add_argument("--out", help="Markdown output path (default: <txt>.md)")
    ap.add_argument("--max_tokens", type=int, default=DEFAULT_MAX_TOKENS)
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    args = ap.parse_args()

    full_summary = process_in_chunks(args.txt)
    
    # Write the final summary to the output file
    out_path = args.out or default_md_path(args.txt)
    Path(out_path).write_text(full_summary, encoding="utf-8")
    logger.info(f"Summary written to {out_path}")

if __name__ == "__main__":
    main()