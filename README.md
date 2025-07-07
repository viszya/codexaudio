
# 🎙️ Continuous Audio Recorder Setup Guide

This guide explains how to set up and run the `continuous_audio_recorder.py` script on **macOS**. The script continuously records audio until stopped (via `Ctrl+C`), saving files as **128kbps stereo MP3s** in daily folders. Each filename includes the date, start time, stop time, timezone offset, and recording number.

---

## 🧰 Prerequisites

- **macOS**: Tested on macOS Ventura, Sonoma.
- **Homebrew**: macOS package manager. Install if not already present.
- **Admin Access**: Required for installations.
- **Audio Hardware**: Microphone and system audio for aggregate device setup.

---

## ⚙️ Setup Instructions

### 1. Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Add Homebrew to your shell path:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
source ~/.zshrc
```

Verify:
```bash
brew --version
```

---

### 2. Install Python 3.12

```bash
brew install python@3.12
python3.12 --version  # Should output Python 3.12.x
```

Note: Python path is typically `/opt/homebrew/bin/python3.12`.

---

### 3. Install FFmpeg

```bash
brew install ffmpeg
ffmpeg -version  # Verify installation
```

---

### 4. Create a Virtual Environment

```bash
/opt/homebrew/bin/python3.12 -m venv ~/codexaudio/venv
source ~/codexaudio/venv/bin/activate  # Activate the environment
```

---

### 5. Install PortAudio and Python Libraries

**Install PortAudio (required for PyAudio):**

```bash
brew install portaudio
```

### 6. Install Python Libraries

```bash
pip install pyaudio pydub
```

Verify:

```bash
pip show pyaudio
pip show pydub
```

- `pyaudio`: For audio recording  
- `pydub`: For converting WAV to MP3

---

### 7. Set Up Aggregate Audio Device

1. Open **Audio MIDI Setup** via Spotlight.
2. Click ➕ and choose **Create Aggregate Device**.
3. Rename it to `System + Mic`.
4. Add:
   - Your **microphone**
   - System output (e.g., **Built-in Output**, **Soundflower**, or **BlackHole**)
5. Ensure:
   - At least **3 input channels**
   - **Sample rate**: `44100 Hz`

> **Note:**  
> To capture system audio, install BlackHole:
> ```bash
> brew install blackhole-2ch
> ```

Add BlackHole to your aggregate device via Audio MIDI Setup.

---

### 8. Configure the Script

1. Save `continuous_audio_recorder.py` to your project directory, e.g.:

```bash
mkdir -p ~/codexaudio
mv continuous_audio_recorder.py ~/codexaudio/
```

2. Edit the script:
```python
base_dir = "/Users/viszya/audio_recordings"  # Update with your preferred path
```

3. Ensure the directory exists and is writable:
```bash
mkdir -p /Users/viszya/audio_recordings
chmod -R u+w /Users/viszya/audio_recordings
```

---

### 9. Run the Script

```bash
cd ~/codexaudio
source venv/bin/activate
python continuous_audio_recorder.py
```

> The script will display:  
> `Recording started. Press Ctrl+C to stop.`  
>  
> Audio files are saved in:  
> `/Users/viszya/audio_recordings/YYYY-MM-DD/`  
> e.g., `20250707_150000-0700_to_151000-0700_1.mp3`

---

## 🧪 Troubleshooting

### 🔒 Read-Only File System Error
- Ensure `base_dir` is writable.
- Run:
  ```bash
  chmod -R u+w /Users/viszya/audio_recordings
  ```

### 🎧 Aggregate Device Not Found
- Recheck the "System + Mic" setup in **Audio MIDI Setup**.
- Confirm name and channel count in script.

### ❌ FFmpeg Errors
- Check FFmpeg accessibility:
  ```bash
  which ffmpeg
  ```
- If not found, reinstall or update your PATH.

### 🔇 No Audio Recorded
- Confirm mic/system audio are active and included in the aggregate device.
- Test input via **Audio MIDI Setup**.

### 💾 Memory Issues
- For long recordings, consider limiting session time to avoid RAM issues.

---

## 📁 File Output

- **Location**:  
  `base_dir/YYYY-MM-DD/`  
  e.g., `/Users/viszya/audio_recordings/2025-07-07/`

- **Filename Format**:  
  `YYYYMMDD_HHMMSS±HHMM_to_HHMMSS±HHMM_N.mp3`  
  Example: `20250707_150000-0700_to_151000-0700_1.mp3`

- **Format**:  
  `128kbps stereo MP3`, converted from a temporary WAV file.

---

## ✅ Requirements Summary

| Category          | Requirement                                |
|-------------------|---------------------------------------------|
| **Software**       | Homebrew, Python 3.12, FFmpeg, BlackHole (optional) |
| **Python Packages**| `pyaudio`, `pydub`                         |
| **Hardware**       | Microphone, optional loopback for system audio |
| **macOS Config**   | Aggregate device: `"System + Mic"`, ≥3 input channels |

---

For help, contact the script maintainer or consult [Python](https://docs.python.org/3/) and [FFmpeg](https://ffmpeg.org/documentation.html) documentation.
