import pyaudio
import wave
from pydub import AudioSegment
import os
from datetime import datetime

# Audio configuration settings
FORMAT = pyaudio.paInt16
CHANNELS = 3  # Adjust based on your aggregate device
RATE = 44100
CHUNK = 1024
base_dir = "/Users/vedant/audio_recordings"  # Specify your base directory here (e.g., "/path/to/recordings")

# Initialize PyAudio
p = pyaudio.PyAudio()

# Find the aggregate device
aggregate_index = None
for i in range(p.get_device_count()):
    dev = p.get_device_info_by_index(i)
    if "System + Mic" in dev["name"]:
        aggregate_index = i
        max_input_channels = dev["maxInputChannels"]
        print(f"Found device: {dev['name']}, Input Channels: {max_input_channels}")
        if max_input_channels < CHANNELS:
            print(f"Error: Device supports only {max_input_channels} channels, but CHANNELS set to {CHANNELS}")
            p.terminate()
            exit()
        break

if aggregate_index is None:
    print("System + Mic not found. Please set up the aggregate device in Audio MIDI Setup.")
    p.terminate()
    exit()

print("Recording started. Press Ctrl+C to stop.")

try:
    # Start recording
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
        input_device_index=aggregate_index
    )

    start_time = datetime.now()
    day_folder = start_time.strftime("%Y-%m-%d")
    folder_path = os.path.join(base_dir, day_folder)
    os.makedirs(folder_path, exist_ok=True)

    # Determine recording number
    mp3_files = [f for f in os.listdir(folder_path) if f.endswith('.mp3')]
    recording_num = len(mp3_files) + 1

    # Generate temporary WAV file path
    wav_path = os.path.join(folder_path, f"temp_{recording_num}.wav")

    # Record audio continuously
    frames = []
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

except KeyboardInterrupt:
    print("Stopping recording")

    # Stop and close the stream
    stream.stop_stream()
    stream.close()
    p.terminate()

    # Generate filenames
    stop_time = datetime.now()
    start_str = start_time.strftime("%Y%m%d_%H%M%S%z")
    stop_str = stop_time.strftime("%H%M%S%z")
    filename = f"{start_str}_to_{stop_str}_{recording_num}.mp3"
    mp3_path = os.path.join(folder_path, filename)

    # Save temporary WAV file
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    # Convert to MP3 and delete WAV
    sound = AudioSegment.from_wav(wav_path)
    sound = sound.set_channels(1)  # Convert to mono
    sound = sound.set_channels(2)  # Convert to stereo
    sound.export(mp3_path, format="mp3", bitrate="256k")
    os.remove(wav_path)

    print(f"Recorded and saved {mp3_path}")

finally:
    # Ensure PyAudio is terminated even if an error occurs
    p.terminate()