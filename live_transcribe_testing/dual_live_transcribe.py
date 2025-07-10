#!/usr/bin/env python3
"""
live_transcribe_dual_calibrated.py — two speaker live transcription for macOS
================================================================================
Captures **built‑in mic** as *Person 1* and **system audio (BlackHole output)**
 as *Person 2*.

What’s new (2025-07-09)
-----------------------
* **Auto switch system output** to BlackHole (or a Multi-Output containing it)
  using the optional **`switchaudio-osx`** CLI.  If the tool isn’t installed we
  fall back to a clear prompt so you can swap devices manually.
* Keeps the per-second VU meters so you can instantly see whether BlackHole is
  receiving signal.
* Small refactor (helper funcs, clearer prints).

Prerequisites
-------------
* **BlackHole 2ch** (or 16ch) installed.
* A *Multi-Output Device* in **Audio MIDI Setup** that bundles
  • built-in speakers / headphones  • BlackHole.
  Name it e.g. **"Spk + BlackHole"**.
* *(Optional but recommended)* `brew install switchaudio-osx` so the script can
  flip the output for you.

Usage
-----
```bash
python live_transcribe_dual_calibrated.py \
       --output "Spk + BlackHole"   # name as it appears in SwitchAudioSource -a
```
If you omit `--output`, the script just looks for any output device whose name
contains "BlackHole"; if nothing matches, you’ll get an interactive prompt.
"""

from __future__ import annotations
import sys, time, math, argparse, subprocess, shutil
from collections import deque

from Foundation import *
from AVFoundation import *
from Speech import *
import pyaudio

AGG_NAME = "System + Mic"
CALIBRATION_SECONDS = 1.5
SILENCE_THRESH = 0.0004  # ~−75 dBFS
SILENCE_TIMEOUT = 3       # warn if BH silent for this many seconds

# ─────────────────── helpers ────────────────────

def switch_system_output(target:str) -> bool:
    """Try to switch macOS system output using switchaudio-osx."""
    exe = shutil.which("SwitchAudioSource")
    if not exe:
        return False
    try:
        subprocess.run([exe, "-s", target], check=True, stdout=subprocess.DEVNULL)
        print(f"🔈  System output set to: {target}")
        return True
    except subprocess.CalledProcessError:
        return False


def find_bh_output_device() -> str | None:
    """Return the first output device containing 'BlackHole' via switchaudio-osx."""
    exe = shutil.which("SwitchAudioSource")
    if not exe:
        return None
    out = subprocess.check_output([exe, "-a"], text=True)
    for line in out.splitlines():
        if "output:" in line and "BlackHole" in line:
            return line.rsplit("output:", 1)[1].strip()
    return None


def rms(arr, n:int) -> float:
    if n == 0:
        return 0.0
    s = 0.0
    for i in range(n):
        s += arr[i] * arr[i]
    return math.sqrt(s / n)

# ─────────────────── arg-parse ───────────────────
parser = argparse.ArgumentParser(description="Two-speaker live transcription (mic + system audio)")
parser.add_argument("--output", metavar="DEVICE", help="Set macOS system output to this device before starting")
opts = parser.parse_args()

# ────────────────── AVAudio session ──────────────
session = AVAudioSession.sharedInstance()
session.requestRecordPermission_(lambda ok: print("Microphone access granted" if ok else "Microphone access denied"))
session.setCategory_error_(AVAudioSessionCategoryPlayAndRecord, None)
session.setActive_error_(True, None)

# ───── attempt to route system audio into BlackHole ─────
output_target = opts.output or find_bh_output_device()
if output_target:
    if not switch_system_output(output_target):
        print(f"⚠️  Could not switch output to '{output_target}'. Do it manually.")
else:
    print("⚠️  No BlackHole-based output device found. Make sure system audio is routed to BlackHole.")

# ───────── locate aggregate input device ─────────
p = pyaudio.PyAudio()
agg_idx = agg_nch = None
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if AGG_NAME in info["name"]:
        agg_idx, agg_nch = i, info["maxInputChannels"]
        break

if agg_idx is None or agg_nch < 3:
    print(f"[ERROR] Aggregate '{AGG_NAME}' not found or has <3 input channels (check Audio MIDI Setup).")
    sys.exit(1)

print(f"✅  Using aggregate input: {AGG_NAME} — {agg_nch} ch")

# ─────────── AVAudioEngine graph ────────────
engine = AVAudioEngine.new()
input_node = engine.inputNode()
src_fmt = input_node.outputFormatForBus_(0)
print("Input format:", src_fmt)

if src_fmt.channelCount() < 3:
    print("[ERROR] Aggregate reports fewer than 3 channels.")
    sys.exit(1)

mono_fmt = AVAudioFormat.alloc().initWithCommonFormat_sampleRate_channels_interleaved_(
    AVAudioPCMFormatFloat32, src_fmt.sampleRate(), 1, False
)

# ─────────── Speech recogniser ────────────
recognizer = SFSpeechRecognizer.alloc().initWithLocale_(NSLocale.localeWithLocaleIdentifier_("en-US"))
if not recognizer.isAvailable():
    print("[ERROR] Speech recognizer unavailable.")
    sys.exit(1)

req1 = SFSpeechAudioBufferRecognitionRequest.new()
req2 = SFSpeechAudioBufferRecognitionRequest.new()

file1 = open("transcription_person1.txt", "w+", encoding="utf-8")
file2 = open("transcription_person2.txt", "w+", encoding="utf-8")

recognizer.recognitionTaskWithRequest_resultHandler_(req1, lambda r,e: (file1.seek(0), file1.write(r.bestTranscription().formattedString()), file1.truncate(), file1.flush(), print(f"P1: {r.bestTranscription().formattedString()}")) if r else e and print("[P1]", e))
recognizer.recognitionTaskWithRequest_resultHandler_(req2, lambda r,e: (file2.seek(0), file2.write(r.bestTranscription().formattedString()), file2.truncate(), file2.flush(), print(f"P2: {r.bestTranscription().formattedString()}")) if r else e and print("[P2]", e))

# ────────── calibration & VU-meter vars ──────────
samples_acc = [0.0, 0.0, 0.0]
samples_cnt = 0
calibrated = False
mic_ch = 2
bh_ch  = (0,1)
calib_start = time.time()

meter_timer = time.time()
last_rms_bh = deque(maxlen=SILENCE_TIMEOUT)

# ─────────── Audio tap callback ────────────

def tap(buffer, when):
    global samples_cnt, samples_acc, calibrated, mic_ch, bh_ch, meter_timer

    n_frames = int(buffer.frameLength())
    if n_frames == 0:
        return

    fc = buffer.floatChannelData()

    # ―― calibration
    if not calibrated:
        for ch in range(3):
            samples_acc[ch] += rms(fc[ch], n_frames)
        samples_cnt += 1
        if time.time() - calib_start >= CALIBRATION_SECONDS:
            avg = [e / samples_cnt for e in samples_acc]
            mic_ch = max(range(3), key=avg.__getitem__)
            bh_ch  = tuple(c for c in range(3) if c != mic_ch)
            calibrated = True
            print(f"\n🔧  Calibration done → mic = CH{mic_ch}, BlackHole = CH{bh_ch}\n")
        return

    # ―― normal operation
    mic  = fc[mic_ch]
    bh_l = fc[bh_ch[0]]
    bh_r = fc[bh_ch[1]]

    # Person 1 (mic)
    buf1 = AVAudioPCMBuffer.alloc().initWithPCMFormat_frameCapacity_(mono_fmt, n_frames)
    buf1.setFrameLength_(n_frames)
    buf1_data = buf1.floatChannelData()[0]
    for i in range(n_frames):
        buf1_data[i] = mic[i]
    req1.appendAudioPCMBuffer_(buf1)

    # Person 2 (BlackHole L+R → mono)
    buf2 = AVAudioPCMBuffer.alloc().initWithPCMFormat_frameCapacity_(mono_fmt, n_frames)
    buf2.setFrameLength_(n_frames)
    buf2_data = buf2.floatChannelData()[0]
    for i in range(n_frames):
        buf2_data[i] = 0.5 * (bh_l[i] + bh_r[i])
    req2.appendAudioPCMBuffer_(buf2)

    # ―― VU meter
    if time.time() - meter_timer >= 1.0:
        rms_mic = rms(mic, n_frames)
        rms_bh  = rms(buf2_data, n_frames)
        print(f"[VU] mic: {rms_mic:.4f}\tBH: {rms_bh:.4f}")
        last_rms_bh.append(rms_bh)
        if len(last_rms_bh) == last_rms_bh.maxlen and all(v < SILENCE_THRESH for v in last_rms_bh):
            print("⚠️  BlackHole looks silent → confirm system output device.")
            last_rms_bh.clear()
        meter_timer = time.time()

input_node.installTapOnBus_bufferSize_format_block_(0, 1024, src_fmt, tap)

# ─────────── run ───────────
engine.prepare()
engine.startAndReturnError_(None)

print("\nSpeak into the MIC during the countdown to calibrate channel mapping…")
for s in range(int(CALIBRATION_SECONDS), 0, -1):
    print(f"  … {s}")
    time.sleep(1)

print("🎙  Live transcription started.  Person-1 = built-in mic; Person-2 = system audio (BlackHole).\n")
NSRunLoop.currentRunLoop().run
