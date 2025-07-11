import os
import logging
from transformers import AutoTokenizer, Gemma3ForConditionalGeneration

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

# Load HF_TOKEN from environment
token = os.getenv('HF_TOKEN')
if not token:
    logger.error('HF_TOKEN not found in environment')
    raise ValueError('HF_TOKEN not found')

logger.info(f"HF_TOKEN: {token[:4]}**** (redacted)")

# Set and verify cache directory
cache_dir = os.getenv('HF_HOME', '/app/models/huggingface')
logger.info(f"Using cache directory: {cache_dir}")

# Ensure cache directory exists and is writable
try:
    os.makedirs(cache_dir, exist_ok=True)
    logger.info(f"Cache directory created/exists: {cache_dir}")
    test_file = os.path.join(cache_dir, "test_write.txt")
    with open(test_file, 'w') as f:
        f.write("test")
    os.remove(test_file)
    logger.info(f"Cache directory is writable")
except Exception as e:
    logger.error(f"Failed to create/write to cache directory {cache_dir}: {e}")
    raise

# Log existing cache contents
try:
    cache_contents = os.listdir(cache_dir)
    logger.info(f"Cache directory contents before download: {cache_contents}")
except Exception as e:
    logger.error(f"Failed to list cache directory {cache_dir}: {e}")
    raise

# Pre-download Gemma model
logger.info("Pre-downloading Gemma model: google/gemma-3-4b-it")
try:
    model = Gemma3ForConditionalGeneration.from_pretrained(
        'google/gemma-3-4b-it',
        torch_dtype='auto',
        cache_dir=cache_dir,
        token=token
    )
    logger.info(f"Gemma model downloaded successfully to {cache_dir}")
    del model  # Free memory
except Exception as e:
    logger.error(f"Failed to download Gemma model: {e}")
    raise

# Pre-download Gemma tokenizer
logger.info("Pre-downloading Gemma tokenizer")
try:
    tokenizer = AutoTokenizer.from_pretrained(
        'google/gemma-3-4b-it',
        use_fast=True,
        cache_dir=cache_dir,
        token=token
    )
    logger.info(f"Gemma tokenizer downloaded successfully to {cache_dir}")
    del tokenizer  # Free memory
except Exception as e:
    logger.error(f"Failed to download Gemma tokenizer: {e}")
    raise

# Verify cache contents after download
try:
    cache_contents = os.listdir(cache_dir)
    logger.info(f"Cache directory contents after download: {cache_contents}")
except Exception as e:
    logger.error(f"Failed to list cache directory {cache_dir}: {e}")
    raise