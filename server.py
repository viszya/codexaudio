import os
import time
import threading
import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from pathlib import Path
from pydantic import BaseModel
import shutil
from dotenv import load_dotenv
import sys
from transcribe import transcribe_file
from summarize import summarize

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)

# Load environment variables
load_dotenv()

# Constants
DEFAULT_MODEL = "google/gemma-3-4b-it"
DEFAULT_TRANSCRIPT_SUFFIX = "_transcript.txt"
DEFAULT_SUMMARY_SUFFIX = "_summary.md"
DEFAULT_TRANSCRIBE_MODEL = "medium.en"
PROCESSING_DIRECTORY = "/app/audio"
MONITOR_INTERVAL = 10  # Seconds between directory checks

# FastAPI App initialization
app = FastAPI()

# File processing request model
class FileProcessingRequest(BaseModel):
    file_path: str

# Process file (transcribe and summarize)
def process_file(file_path: str, transcribe_model: str = DEFAULT_TRANSCRIBE_MODEL, summarize_model: str = DEFAULT_MODEL):
    """Process an MP3 file by transcribing and summarizing it"""
    logger.info(f"Processing file: {file_path}")
    try:
        transcribe_file(file_path, transcribe_model)
        transcript_path = file_path.rsplit(".", 1)[0] + DEFAULT_TRANSCRIPT_SUFFIX
        if os.path.exists(transcript_path):
            summarize(transcript_path, model_id=summarize_model)
            logger.info(f"Generated summary for: {transcript_path}")
        else:
            logger.warning(f"Transcript not found: {transcript_path}")
    except Exception as e:
        logger.error(f"Error processing {file_path}: {str(e)}")

# Check and generate summaries for existing transcripts
def check_and_summarize_transcripts(directory: str, summarize_model: str = DEFAULT_MODEL):
    """Check for transcript files without summaries and generate them"""
    for dirpath, _, filenames in os.walk(directory):
        for file in filenames:
            if file.endswith(DEFAULT_TRANSCRIPT_SUFFIX):
                transcript_path = os.path.join(dirpath, file)
                summary_path = transcript_path.rsplit(".", 1)[0] + DEFAULT_SUMMARY_SUFFIX
                if not os.path.exists(summary_path):
                    logger.info(f"Found transcript without summary: {transcript_path}")
                    try:
                        summarize(transcript_path, model_id=summarize_model)
                        logger.info(f"Generated summary: {summary_path}")
                    except Exception as e:
                        logger.error(f"Error summarizing {transcript_path}: {str(e)}")

# API to process an MP3 file (transcribe and summarize)
@app.post("/process/")
async def process_file_endpoint(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """API to process an MP3 file (transcribe and summarize)"""
    if not file.filename.endswith(".mp3"):
        raise HTTPException(status_code=400, detail="File must be an MP3")
    temp_file_path = f"/tmp/{file.filename}"
    with open(temp_file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    background_tasks.add_task(process_file, temp_file_path)
    return {"message": f"Started processing for {file.filename}"}

# API to transcribe an MP3 file
@app.post("/transcribe/")
async def transcribe_file_endpoint(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """API to transcribe an MP3 file"""
    if not file.filename.endswith(".mp3"):
        raise HTTPException(status_code=400, detail="File must be an MP3")
    temp_file_path = f"/tmp/{file.filename}"
    with open(temp_file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    background_tasks.add_task(transcribe_file, temp_file_path, DEFAULT_TRANSCRIBE_MODEL)
    return {"message": f"Started transcription for {file.filename}"}

# API to summarize a transcript
@app.post("/summarize/")
async def summarize_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """API to summarize a transcript"""
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="File must be a TXT file")
    temp_file_path = f"/tmp/{file.filename}"
    with open(temp_file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    background_tasks.add_task(summarize, temp_file_path)
    return {"message": f"Started summarization for {file.filename}"}

# Endpoint to check the server status
@app.get("/status/")
async def get_status():
    """Check server status"""
    return {"status": "Server is running."}

# Background task to monitor directory for new files and check transcripts
def monitor_directory(directory: str, interval: int = MONITOR_INTERVAL):
    """Monitor the directory and process new MP3 files and check transcripts"""
    logger.info(f"Starting directory monitoring for {directory} with interval {interval}s")
    processed_files = set()
    while True:
        try:
            # Process new MP3 files
            for dirpath, _, filenames in os.walk(directory):
                for file in filenames:
                    file_path = os.path.join(dirpath, file)
                    if file_path not in processed_files and file.endswith(".mp3"):
                        logger.info(f"Found new MP3 file: {file_path}")
                        processed_files.add(file_path)
                        process_file(file_path)
            
            # Check for transcripts needing summaries
            check_and_summarize_transcripts(directory)
            
            time.sleep(interval)
        except Exception as e:
            logger.error(f"Error in directory monitoring: {str(e)}")
            time.sleep(interval)

# Start monitoring directory when FastAPI app starts
@app.on_event("startup")
async def start_monitoring():
    """Start directory monitoring upon FastAPI startup"""
    if not os.path.exists(PROCESSING_DIRECTORY):
        logger.warning(f"Directory {PROCESSING_DIRECTORY} does not exist, creating it")
        os.makedirs(PROCESSING_DIRECTORY)
    logger.info(f"Starting monitoring thread for {PROCESSING_DIRECTORY}")
    monitor_thread = threading.Thread(target=monitor_directory, args=(PROCESSING_DIRECTORY,))
    monitor_thread.daemon = True
    monitor_thread.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)