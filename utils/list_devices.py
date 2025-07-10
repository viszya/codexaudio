import pyaudio

def list_input_devices():
    p = pyaudio.PyAudio()
    
    # Get the number of audio devices
    device_count = p.get_device_count()
    
    print("Available Audio Input Devices:")
    print("-" * 50)
    
    # Iterate through all audio devices
    for i in range(device_count):
        device_info = p.get_device_info_by_index(i)
        
        # Only show input devices (maxInputChannels > 0)
        if device_info['maxInputChannels'] > 0:
            print(f"Device ID: {i}")
            print(f"Device Name: {device_info['name']}")
            print(f"Input Channels: {device_info['maxInputChannels']}")
            print(f"Sample Rate: {int(device_info['defaultSampleRate'])} Hz")
            print("-" * 50)
    
    # Clean up
    p.terminate()

if __name__ == "__main__":
    list_input_devices()
