# MP3 Transcription Script

This script automatically transcribes `.mp3` files in a `recordings` folder using OpenAI Whisper and outputs the results as JSON files. It only processes files that do not already have a corresponding transcript.

## Features
- Processes all `.mp3` files in the `recordings` directory that do not have a corresponding `_transcript.json` file.
- Outputs only the transcript as a JSON file per MP3 (e.g., `yourfile_transcript.json`).
- Skips files that have already been transcribed.
- Shows a progress bar and live elapsed time for each file.
- Estimates processing time for new files based on previous runs (if `.transcribe_stats.json` is present).
- Optionally displays MP3 duration if `mutagen` is installed.
- Exits automatically when done.

## Setup Instructions

### 1. Install Python 3.8+
- Download and install Python from [python.org](https://www.python.org/downloads/) if you don't already have it.
- On macOS, the official installer is recommended.

### 2. Clone or Download This Repository
```
git clone <your-repo-url>
cd <your-repo-directory>
```

### 3. Create the `recordings` Folder
```
mkdir recordings
```
Place your `.mp3` files inside this folder.

### 4. Install Required Python Packages
It is recommended to use a virtual environment:
```
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
Then install dependencies:
```
pip install openai-whisper tqdm
```

#### (Optional) For MP3 duration display:
```
pip install mutagen
```

### 5. Run the Script
```
python3 Transcribe.py
```

- The script will process all `.mp3` files in the `recordings` folder that do not already have a `_transcript.json` file.
- Transcripts will be saved as `<originalfilename>_transcript.json` in the same folder.
- The script will estimate processing time for new files based on previous runs if `.transcribe_stats.json` is present (created automatically after processing qualifying files).

## Notes
- The first run will download the Whisper model (can be several GBs, requires internet connection).
- For best results, use short, clear audio files.
- If you add new `.mp3` files later, just re-run the script.
- The `.transcribe_stats.json` file is used for time estimation and is created/updated automatically.

## Troubleshooting
- If you see SSL certificate errors on macOS, run the `Install Certificates.command` script in your `/Applications/Python 3.x/` folder.
- If you see missing package errors, ensure you are using the correct Python environment and have installed all dependencies.
- If you want MP3 duration display, install `mutagen` as shown above.

## License
MIT 