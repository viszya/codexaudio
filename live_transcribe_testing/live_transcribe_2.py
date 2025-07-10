#!/usr/bin/env python3
"""
dual_input_transcription.py  – built-in mic + BlackHole (Aggregate 3-ch)
-----------------------------------------------------------------------
Person 1 → channel 0  (built-in mic, mono)  →  person1.txt
Person 2 → channels 1 & 2 averaged          →  person2.txt
"""
from __future__ import annotations
import sys, ctypes
from Foundation import NSRunLoop, NSLocale
from AVFoundation import *
from Speech import *
import pyaudio

TARGET_AGGREGATE_NAME = "System + Mic"      # ← change if your Aggregate’s name differs
BUFFER_SIZE           = 1024                # frames per tap
SAMPLE_RATE           = 44_100.0            # Hz

# ── 1. Mic permission ───────────────────────────────────────────────────────
session = AVAudioSession.sharedInstance()
# if not session.requestRecordPermission_(lambda g: None):
#     print("❌ Microphone permission denied."); sys.exit(1)

# ── 2. Locate Aggregate device via PyAudio ──────────────────────────────────
p = pyaudio.PyAudio()
agg_index = next( (i for i in range(p.get_device_count())
                   if TARGET_AGGREGATE_NAME in p.get_device_info_by_index(i)["name"]),
                  None )
if agg_index is None:
    print(f"❌ Aggregate device '{TARGET_AGGREGATE_NAME}' not found."); sys.exit(1)
agg_name = p.get_device_info_by_index(agg_index)["name"]
print(f"✓ Using aggregate device: {agg_name}")

# ── 3. Configure AVAudioSession category & *attempt* preferred input ───────
session.setCategory_error_(AVAudioSessionCategoryPlayAndRecord, None)
session.setActive_error_(True, None)

matched = False
print("\n🔍 AVAudioSession inputs:")
for port in session.availableInputs() or []:
    print(f"   • {port.portName():<30} ({port.portType()})")
    if port.portName() == agg_name:
        matched = session.setPreferredInput_error_(port, None) is None
if not matched:
    print("⚠️  Aggregate device not in AVAudioSession; continuing with system default.\n"
          "   Pick it manually in System Settings ▸ Sound ▸ Input to force it.")

# ── 4. Prepare two Speech recognizers & requests ───────────────────────────
locale = NSLocale.localeWithLocaleIdentifier_("en-US")
rec1, rec2 = (SFSpeechRecognizer.alloc().initWithLocale_(locale) for _ in range(2))
if not (rec1.isAvailable() and rec2.isAvailable()):
    print("❌ Speech recognition unavailable."); sys.exit(1)

req1, req2 = SFSpeechAudioBufferRecognitionRequest.new(), SFSpeechAudioBufferRecognitionRequest.new()
req1.shouldReportPartialResults = True
req2.shouldReportPartialResults = True
f1, f2 = (open(fname, "w+", encoding="utf-8") for fname in ("person1.txt", "person2.txt"))

def mk_handler(fp):
    def _handler(result, error):
        if result:
            fp.seek(0); fp.write(result.bestTranscription().formattedString())
            fp.truncate(); fp.flush()
        elif error:
            # Ignore “no speech” warnings; show others
            if error.code() != 1110:
                print("Recognition error:", error.localizedDescription())
    return _handler

rec1.recognitionTaskWithRequest_resultHandler_(req1, mk_handler(f1))
rec2.recognitionTaskWithRequest_resultHandler_(req2, mk_handler(f2))

# ── 5. Helper: convert PyObjC channel pointer → raw int address ────────────
def addr(channel_ptr) -> int:
    """Return integer (void*) address from PyObjC varlist element."""
    return ctypes.cast(channel_ptr, ctypes.c_void_p).value

# ── 6. Copy / average helpers (operate on raw addresses) ───────────────────
def memcpy_f32(dst_addr, src_addr, frames):
    ctypes.memmove(dst_addr, src_addr, frames * 4)      # 4 bytes / float32

def avg_f32(dst_addr, src1_addr, src2_addr, frames):
    src1 = (ctypes.c_float * frames).from_address(src1_addr)
    src2 = (ctypes.c_float * frames).from_address(src2_addr)
    dst  = (ctypes.c_float * frames).from_address(dst_addr)
    for i in range(frames):
        dst[i] = 0.5 * (src1[i] + src2[i])

# ── 7. AVAudioEngine tap (3-ch → two mono buffers) ─────────────────────────
engine     = AVAudioEngine.alloc().init()
input_node = engine.inputNode()
fmt3       = input_node.outputFormatForBus_(0)
if fmt3.channelCount() != 3:
    print("❌ Expected 3-channel input; found", fmt3.channelCount()); sys.exit(1)

mono_fmt = AVAudioFormat.alloc().initStandardFormatWithSampleRate_channels_(SAMPLE_RATE, 1)

def tap_cb(buffer, when):
    frames   = buffer.frameLength()
    ch_data  = buffer.floatChannelData()
    ch0_ptr  = addr(ch_data[0])
    ch1_ptr  = addr(ch_data[1])
    ch2_ptr  = addr(ch_data[2])

    # Person 1 (built-in mic)
    buf1 = AVAudioPCMBuffer.alloc().initWithPCMFormat_frameCapacity_(mono_fmt, frames)
    buf1.frameLength = frames
    memcpy_f32(addr(buf1.floatChannelData()[0]), ch0_ptr, frames)
    req1.appendAudioPCMBuffer_(buf1)

    # Person 2 (BlackHole stereo → mono)
    buf2 = AVAudioPCMBuffer.alloc().initWithPCMFormat_frameCapacity_(mono_fmt, frames)
    buf2.frameLength = frames
    avg_f32(addr(buf2.floatChannelData()[0]), ch1_ptr, ch2_ptr, frames)
    req2.appendAudioPCMBuffer_(buf2)

input_node.installTapOnBus_bufferSize_format_block_(0, BUFFER_SIZE, fmt3, tap_cb)
engine.prepare(); engine.startAndReturnError_(None)

print("\n🎤  Listening …")
print("    • Person 1 → built-in mic  → person1.txt")
print("    • Person 2 → BlackHole     → person2.txt")
NSRunLoop.currentRunLoop().run()
