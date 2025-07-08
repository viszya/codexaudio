import whisper
import os
from tqdm import tqdm
import json
from datetime import datetime
import time

# Function to get MP3 duration using mutagen if available
mutagen_available = None  # None = not checked yet, True/False = checked

def get_mp3_duration(path):
    global mutagen_available
    if mutagen_available is False:
        return 0
    try:
        from mutagen.mp3 import MP3
        mutagen_available = True
        audio = MP3(path)
        return audio.info.length
    except ImportError:
        mutagen_available = False
        return 0
    except Exception:
        return 0

RECORDINGS_DIR = "./recordings"
STATS_FILE = os.path.join(RECORDINGS_DIR, ".transcribe_stats.json")

# Load Whisper model (medium.en for English, ~1.5 GB)
model = whisper.load_model("medium.en")

# Find all .mp3 files in the recordings directory
mp3_files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith('.mp3')]

# Filter to only those without a corresponding _transcript.json
files_to_process = []
for mp3_file in mp3_files:
    base_name = os.path.splitext(mp3_file)[0]
    transcript_path = os.path.join(RECORDINGS_DIR, f"{base_name}_transcript.json")
    if not os.path.exists(transcript_path):
        files_to_process.append(mp3_file)
    else:
        print(f"Skipping {mp3_file}: transcript already exists.")

# Load stats if available
stats = []
if os.path.exists(STATS_FILE):
    try:
        with open(STATS_FILE, 'r') as f:
            stats = json.load(f)
    except Exception:
        stats = []

if not files_to_process:
    print("No new MP3 files to process.")
else:
    if mutagen_available is False:
        print("[INFO] 'mutagen' not installed. MP3 durations will be shown as 'unknown'. To enable duration display, run: pip install mutagen")
    total_files = len(files_to_process)
    times = []
    for idx, mp3_file in enumerate(files_to_process, 1):
        mp3_path = os.path.join(RECORDINGS_DIR, mp3_file)
        base_name = os.path.splitext(mp3_file)[0]
        # Get duration
        duration = 0
        try:
            duration = get_mp3_duration(mp3_path)
        except Exception:
            pass
        if duration:
            print(f"Processing {mp3_file} (duration: {duration/60:.2f} min)...")
        else:
            print(f"Processing {mp3_file} (duration: unknown)...")
        # Estimate time before starting
        file_size_mb = os.path.getsize(mp3_path) / (1024 * 1024)
        avg_sec_per_mb = None
        valid_stats = [s for s in stats if s.get('size_mb', 0) > 0.5 and s.get('time_sec', 0) > 5]
        if valid_stats:
            avg_sec_per_mb = sum(s['time_sec']/s['size_mb'] for s in valid_stats) / len(valid_stats)
        if avg_sec_per_mb is not None:
            est_time = avg_sec_per_mb * file_size_mb
            print(f"Estimated time for this file: {est_time/60:.2f} min (based on previous runs)")
        else:
            print(f"Estimated time remaining: unknown (processing first file)")
        # Live spinner/progress message with elapsed time
        start = time.time()
        with tqdm(total=0, desc=f"Transcribing {mp3_file} | Elapsed: 0.0s", bar_format="{l_bar}{bar}| {desc}", leave=False) as spinner:
            # Update spinner every second while transcribing
            import threading
            stop_spinner = False
            def update_spinner():
                while not stop_spinner:
                    elapsed = time.time() - start
                    spinner.set_description_str(f"Transcribing {mp3_file} | Elapsed: {elapsed:.1f}s")
                    spinner.refresh()
                    time.sleep(1)
            t = threading.Thread(target=update_spinner)
            t.start()
            result = model.transcribe(mp3_path, word_timestamps=True)
            stop_spinner = True
            t.join()
        elapsed = time.time() - start
        times.append(elapsed)
        # Save minimal text+words result (per file)
        minimal = {"text": result.get("text", "")}
        words = []
        if "segments" in result:
            for seg in result["segments"]:
                if isinstance(seg, dict):
                    for w in seg.get("words", []):
                        word = w.get("word")
                        if word is not None:
                            words.append(word)
        if words:
            minimal["words"] = words
        transcript_path = os.path.join(RECORDINGS_DIR, f"{base_name}_transcript.json")
        with open(transcript_path, 'w') as f:
            json.dump(minimal, f, indent=2)
        print(f"Saved transcript: {transcript_path}")
        print(f"Time taken: {elapsed:.2f} seconds.")
        # Save/update stats
        if file_size_mb > 0.5 and elapsed > 5:
            stats.append({'size_mb': file_size_mb, 'time_sec': elapsed})
            try:
                with open(STATS_FILE, 'w') as f:
                    json.dump(stats, f)
            except Exception:
                pass
        # Estimate time remaining for batch
        avg_time = sum(times) / len(times)
        files_left = total_files - idx
        if files_left > 0:
            eta = avg_time * files_left
            print(f"Estimated time remaining: {eta/60:.2f} min for {files_left} file(s).")
    print("All files processed.")