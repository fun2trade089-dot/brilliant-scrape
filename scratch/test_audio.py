# -*- coding: utf-8 -*-
import sys
import time
import wave
import pyaudiowpatch as pyaudio

def test_record():
    p = pyaudio.PyAudio()
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    except OSError:
        print("WASAPI API not available.")
        return

    # Find the loopback device
    loopback_dev = None
    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
    
    if default_speakers.get("isLoopbackDevice"):
        loopback_dev = default_speakers
    else:
        for loopback in p.get_loopback_device_info_generator():
            if default_speakers["name"] in loopback["name"]:
                loopback_dev = loopback
                break
        if not loopback_dev:
            # Fallback to any loopback device
            for idx in range(p.get_device_count()):
                dev = p.get_device_info_by_index(idx)
                if dev.get("isLoopbackDevice"):
                    loopback_dev = dev
                    break

    if not loopback_dev:
        print("No loopback device found.")
        return

    print(f"Recording from: {loopback_dev['name']} (Index {loopback_dev['index']})")
    
    filename = "test_audio.wav"
    channels = loopback_dev["maxInputChannels"]
    rate = int(loopback_dev["defaultSampleRate"])
    
    stream = p.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=rate,
        input=True,
        input_device_index=loopback_dev["index"],
        frames_per_buffer=1024
    )
    
    frames = []
    print("Recording 3 seconds...")
    for _ in range(0, int(rate / 1024 * 3)):
        data = stream.read(1024)
        frames.append(data)
        
    print("Done recording.")
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    wf = wave.open(filename, 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    wf.setframerate(rate)
    wf.writeframes(b''.join(frames))
    wf.close()
    print(f"Saved to {filename}")

if __name__ == "__main__":
    test_record()
