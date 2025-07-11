#!/usr/bin/env python3
"""
live_transcribe.py – capture the “System + Mic” aggregate device, fold it to
mono, and stream to Apple Speech.  Works on macOS 14, Python 3.12,
PyObjC ≥ 10.3, NumPy, PyAudio.
"""

import ctypes, threading
import numpy as np, pyaudio
from Foundation   import NSLocale, NSRunLoop
from AVFoundation import (AVAudioSession, AVAudioFormat,
                          AVAudioPCMBuffer, AVAudioPCMFormatInt16)
from Speech       import (SFSpeechRecognizer,
                          SFSpeechAudioBufferRecognitionRequest)

# --------------------------------------------------------------------------
DEVICE   = "System + Mic"   # exact name in Audio MIDI Setup
RATE     = 44_100           # Hz
CHUNK    = 1_024            # frames per PyAudio read
# --------------------------------------------------------------------------

# 1  Core-Audio session
sess = AVAudioSession.sharedInstance()
# if not sess.requestRecordPermission_(lambda g: None):
#     raise RuntimeError("Microphone permission denied")
sess.setCategory_error_("AVAudioSessionCategoryPlayAndRecord", None)
sess.setPreferredSampleRate_error_(RATE, None)
sess.setActive_error_(True, None)

# 2  Find aggregate device
pa = pyaudio.PyAudio()
index = ch_in = None
for i in range(pa.get_device_count()):
    d = pa.get_device_info_by_index(i)
    if DEVICE in d["name"]:
        index, ch_in = i, d["maxInputChannels"]
        print(f"✓  Using “{d['name']}” – {ch_in} channels")
        break
if index is None:
    raise RuntimeError(f'Aggregate device “{DEVICE}” not found')

# 3  PyAudio stream
stream = pa.open(format=pyaudio.paInt16, channels=ch_in, rate=RATE,
                 input=True, frames_per_buffer=CHUNK, input_device_index=index)

# 4  Speech recognizer
recog = SFSpeechRecognizer.alloc().initWithLocale_(
    NSLocale.localeWithLocaleIdentifier_("en-US")
)
if not recog or not recog.isAvailable():
    raise RuntimeError("SFSpeechRecognizer unavailable")

req = SFSpeechAudioBufferRecognitionRequest.new()
req.setShouldReportPartialResults_(True)

def on_result(res, err):
    if res:
        print("\r" + res.bestTranscription().formattedString(), end="", flush=True)
    elif err:
        print("Recognition error:", err)

recog.recognitionTaskWithRequest_resultHandler_(req, on_result)

# 5  Target format: mono, 16-bit, **non-interleaved**
fmt = AVAudioFormat.alloc(
).initWithCommonFormat_sampleRate_channels_interleaved_(
    AVAudioPCMFormatInt16, float(RATE), 1, False
)

# 6  Feed thread
def feed():
    while True:
        raw = stream.read(CHUNK, exception_on_overflow=False)

        mono = np.frombuffer(raw, np.int16).reshape(-1, ch_in).mean(axis=1)
        mono = np.rint(mono).astype(np.int16, copy=False)
        frames = mono.size

        buf = AVAudioPCMBuffer.alloc().initWithPCMFormat_frameCapacity_(fmt, frames)
        buf.setFrameLength_(frames)

        # --- FIX: get raw address with __c_void_p__ ------------------------
        chan_ptr = buf.int16ChannelData()[0]            # OpaquePointer proxy
        addr     = chan_ptr.__c_void_p__().value        # <-- ONE-LINE FIX
        dest     = (ctypes.c_int16 * frames).from_address(addr)
        dest[:]  = mono
        # ------------------------------------------------------------------

        req.appendAudioPCMBuffer_(buf)

threading.Thread(target=feed, daemon=True).start()

# 7  Run until Ctrl-C
print("\nListening…  (Ctrl-C to quit)\n")
try:
    NSRunLoop.currentRunLoop().run()
except KeyboardInterrupt:
    pass
finally:
    stream.stop_stream(); stream.close(); pa.terminate()
    print("\nStopped.")
