#!/usr/bin/env python3
"""dual_input_transcription.py — macOS, two inputs, auto-mono down-mix
===========================================================================
• **Person 1** → MacBook Pro Mic (1-ch float32, 44,100 Hz)
• **Person 2** → BlackHole 2ch (2-ch float32, 44,100 Hz)

Transcribes audio from two separate input devices using PyAudio and Apple's
Speech framework, downmixing to mono when necessary.
"""
from __future__ import annotations
import ctypes, sys, os, time, queue, threading, datetime as _dt
from ctypes import c_void_p
from typing import List, Tuple
import objc
from Foundation import *
from AVFoundation import *
from Speech import *
import pyaudio


# ────────── Config ──────────
LOCALE             = "en-US"
RATE               = 44_100   # Hz
PA_FORMAT          = pyaudio.paFloat32   # 32-bit float
BYTES_PER_SAMPLE   = 4
FRAMES_PER_BUFFER  = 2048     # 46 ms
TRANSCRIPT_FILE    = "transcription.txt"

DEVICES = [
    ("MacBook Pro Microphone", "Person 1"),
    ("BlackHole 2ch",          "Person 2"),
]

conversation_lock = threading.Lock()
conversation: List[Tuple[float, str, str]] = []
audio = pyaudio.PyAudio()

# ───── Cocoa Exception Handler ─────
def _objc_exc(ptr):
    try:
        NSLog("🔴 Cocoa exception: %@", objc.objc_object(c_void_p=ptr))
    except Exception:
        print("🔴 Obj-C exception @", ptr)
try:
    objc.setUncaughtExceptionHandler(_objc_exc)
except AttributeError:
    pass

# ───── Permission Check ─────
def _await(pred, timeout=30):
    rl, end = NSRunLoop.currentRunLoop(), time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        rl.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))
    return False

def ensure_permissions():
    spev, spstatus = threading.Event(), [None]
    miev, mirok = threading.Event(), [False]
    SFSpeechRecognizer.requestAuthorization_(lambda st: (spstatus.__setitem__(0, st), spev.set()))
    AVAudioSession.sharedInstance().requestRecordPermission_(lambda g: (mirok.__setitem__(0, g), miev.set()))
    if not _await(lambda: spev.is_set() and miev.is_set()):
        print("❌ Permission dialogs timed out"); sys.exit(1)
    if spstatus[0] != SFSpeechRecognizerAuthorizationStatusAuthorized:
        print("❌ Speech permission denied"); sys.exit(1)
    if not mirok[0]:
        print("❌ Microphone permission denied"); sys.exit(1)

# ───── Device Discovery ─────
def find_device(name_sub: str):
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0 and name_sub.lower() in info["name"].lower():
            print(f"   ↳ {info['name']} → index {i}, channels {info['maxInputChannels']}")
            return i, info["maxInputChannels"]
    raise RuntimeError(f"Input '{name_sub}' not found")

# ───── File Flush ─────
def flush():
    with open(TRANSCRIPT_FILE, "w", encoding="utf-8") as f:
        for ts, who, txt in conversation:
            f.write(f"[{_dt.datetime.fromtimestamp(ts).strftime('%H:%M:%S')}] {who}: {txt}\n")

# ───── Worker ─────
class RecognitionWorker(threading.Thread):
    def __init__(self, dev_idx: int, in_channels: int, label: str):
        super().__init__(daemon=True)
        self.dev_idx, self.inch, self.label = dev_idx, in_channels, label
        self.q: "queue.Queue[bytes]" = queue.Queue()
        self.stop_evt = threading.Event()
        self.av_format = AVAudioFormat.alloc().initStandardFormatWithSampleRate_channels_(RATE, 1)
        self.recog = SFSpeechRecognizer.alloc().initWithLocale_(NSLocale.localeWithLocaleIdentifier_(LOCALE))
        self.request = SFSpeechAudioBufferRecognitionRequest.new()
        self.request.setShouldReportPartialResults_(True)

    def _callback(self, data, *_):
        self.q.put(data)
        return (None, pyaudio.paContinue)

    def _downmix_to_mono(self, raw: bytes) -> bytes:
        if self.inch == 1:
            return raw
        samples = memoryview(raw).cast('f')
        frames = len(samples) // self.inch
        mono = bytearray(frames * BYTES_PER_SAMPLE)
        out_mv = memoryview(mono).cast('f')
        for i in range(frames):
            acc = 0.0
            for ch in range(self.inch):
                acc += samples[i * self.inch + ch]
            out_mv[i] = acc / self.inch
        return mono

    def _result(self, res, err):
        if err or not res:
            return
        txt = res.bestTranscription().formattedString()
        with conversation_lock:
            conversation.append((time.time(), self.label, txt))
            conversation.sort(key=lambda t: t[0])
            flush()
            print(f"[{self.label}] → {txt}")

    def run(self):
        stream = audio.open(
            format=PA_FORMAT,
            channels=self.inch,
            rate=RATE,
            input=True,
            input_device_index=self.dev_idx,
            frames_per_buffer=FRAMES_PER_BUFFER,
            stream_callback=self._callback
        )
        stream.start_stream()
        self.recog.recognitionTaskWithRequest_resultHandler_(self.request, self._result)
        while not self.stop_evt.is_set():
            try:
                raw = self.q.get(timeout=0.05)
                mono_raw = self._downmix_to_mono(raw)
                frames = len(mono_raw) // BYTES_PER_SAMPLE
                pcm = AVAudioPCMBuffer.alloc().initWithPCMFormat_frameCapacity_(self.av_format, frames)
                pcm.setFrameLength_(frames)
                channel_data = pcm.floatChannelData()[0]
                mono_mv = memoryview(mono_raw).cast('f')
                for i in range(frames):
                    channel_data[i] = mono_mv[i]
                self.request.appendAudioPCMBuffer_(pcm)
            except queue.Empty:
                pass
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.01))
        stream.stop_stream()
        stream.close()

    def stop(self):
        self.stop_evt.set()

# ───── Main ─────
def main():
    print("🗣  Checking permissions…")
    #ensure_permissions()
    workers = []
    for name_sub, label in DEVICES:
        try:
            idx, chans = find_device(name_sub)
        except RuntimeError as e:
            print("❌", e); sys.exit(1)
        workers.append(RecognitionWorker(idx, chans, label))
    for w in workers:
        w.start()
    print("🎤  Listening… (Ctrl-C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for w in workers:
            w.stop()
            w.join()
        audio.terminate()
        flush()
        print("📄 Transcript →", os.path.abspath(TRANSCRIPT_FILE))

if __name__ == "__main__":
    main()