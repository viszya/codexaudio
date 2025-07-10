import os
import argparse
from pathlib import Path
import subprocess
import http.server
import socketserver
import threading
import shutil
import time

# Default configurations
DEFAULT_MODEL = "google/gemma-3-4b-it"
DEFAULT_PROMPT = Path("prompt.txt").read_text(encoding="utf-8")
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.1
DEFAULT_TRANSCRIPT_SUFFIX = "_transcript.txt"
DEFAULT_SUMMARY_SUFFIX = "_summary.md"
DEFAULT_TRANSCRIBE_MODEL = "medium.en"

# Path to the scripts
scripts_dir = '/Users/viszya/Developer/Programs/Python/codexaudio'

# Ensure that we're always in the correct directory for the scripts
os.chdir(scripts_dir)

# Function to transcribe an MP3 file using Whisper (transcribe.py functionality)
def transcribe(file: str, model: str = DEFAULT_TRANSCRIBE_MODEL):
    print(f"Running transcription for {file}...")
    command = [
        "python3", "transcribe.py", file, "--model", model
    ]
    subprocess.run(command, cwd=scripts_dir)  # Ensure the subprocess runs in the correct directory

# Function to summarize a transcript (summarize.py functionality)
def summarize(txt_file: str, model: str = DEFAULT_MODEL, prompt: str = DEFAULT_PROMPT, 
             max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float = DEFAULT_TEMPERATURE):
    print(f"Running summarization for {txt_file}...")
    command = [
        "python3", "summarize.py", txt_file, "--model", model, "--prompt", prompt,
        "--max_tokens", str(max_tokens), "--temperature", str(temperature)
    ]
    subprocess.run(command, cwd=scripts_dir)  # Ensure the subprocess runs in the correct directory

# Function to process a single file
def process_file(file_path: str):
    if file_path.endswith(".mp3"):
        transcript_path = file_path.replace(".mp3", DEFAULT_TRANSCRIPT_SUFFIX)
        summary_path = file_path.replace(".mp3", DEFAULT_SUMMARY_SUFFIX)

        # Check if the transcript exists
        if not os.path.exists(transcript_path):
            print(f"Transcribing {file_path}...")
            transcribe(file_path)
        else:
            print(f"Transcript exists for {file_path}, skipping transcription.")

        # Check if the summary exists
        if not os.path.exists(summary_path):
            print(f"Summarizing {transcript_path}...")
            summarize(transcript_path)
        else:
            print(f"Summary exists for {file_path}, skipping summarization.")

# Function to process files in the directory (including subdirectories)
def process_files(directory: str):
    # Walk through all files in the directory and subdirectories
    for dirpath, _, filenames in os.walk(directory):
        for file in filenames:
            file_path = os.path.join(dirpath, file)
            process_file(file_path)

# Function to monitor directory for new files and process them
def monitor_directory(directory: str, interval: int = 10):
    processed_files = set()

    while True:
        # Check and process files
        print(f"Checking for new files in {directory}...")
        for dirpath, _, filenames in os.walk(directory):
            for file in filenames:
                file_path = os.path.join(dirpath, file)
                if file_path not in processed_files and file.endswith(".mp3"):
                    processed_files.add(file_path)
                    process_file(file_path)

        # Wait for the next interval
        time.sleep(interval)

# Setup and start the local server
def run_local_server(directory: str, port: int = 8000):
    os.chdir(directory)  # Change the directory to the working directory
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", port), handler)
    print(f"Serving files in {directory} on port {port}")
    httpd.serve_forever()

# Function to run the whole process: transcribe or summarize based on files in the directory
def run(directory: str):
    print(f"Processing directory: {directory}")
    process_files(directory)
    print("All files processed. Starting local server...")
    
    # Start the local server in a separate thread
    server_thread = threading.Thread(target=run_local_server, args=(directory,))
    server_thread.daemon = True
    server_thread.start()

    # Monitor the directory for new files
    monitor_thread = threading.Thread(target=monitor_directory, args=(directory,))
    monitor_thread.daemon = True
    monitor_thread.start()

    # Wait for the server and monitor thread to finish
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Server and monitor stopped.")

# Main function to accept command-line arguments and run the process
def main():
    parser = argparse.ArgumentParser(description="Process MP3 files in a directory for transcription and summarization.")
    parser.add_argument("directory", help="Directory to scan for MP3 files")
    parser.add_argument("--port", type=int, default=8000, help="Port for local server (default: 8000)")
    args = parser.parse_args()

    run(args.directory)

if __name__ == "__main__":
    main()
