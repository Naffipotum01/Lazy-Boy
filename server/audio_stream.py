import threading
import struct
import time


class AudioStreamer:
    def __init__(self):
        self._play_thread = None
        self._running = False
        self._pyaudio = None
        self._stream_in = None
        self._stream_out = None
        self._send_callback = None
        self._format = None
        self._channels = 1
        self._rate = 16000
        self._chunk = 3200

    def start_playback(self):
        try:
            import pyaudio as pa
            self._pyaudio = pa
            p = pa.PyAudio()
            self._stream_out = p.open(
                format=pa.paInt16,
                channels=self._channels,
                rate=self._rate,
                output=True,
                frames_per_buffer=self._chunk,
            )
            self._running = True
            return True
        except Exception as e:
            print(f"[!] Audio playback unavailable: {e}")
            return False

    def start_capture(self, send_callback):
        try:
            import pyaudio as pa
            self._pyaudio = pa
            self._send_callback = send_callback
            p = pa.PyAudio()
            self._stream_in = p.open(
                format=pa.paInt16,
                channels=self._channels,
                rate=self._rate,
                input=True,
                frames_per_buffer=self._chunk,
            )
            self._running = True
            self._play_thread = threading.Thread(
                target=self._capture_loop, daemon=True
            )
            self._play_thread.start()
            return True
        except Exception as e:
            print(f"[!] Audio capture unavailable: {e}")
            return False

    def _capture_loop(self):
        while self._running and self._stream_in:
            try:
                data = self._stream_in.read(self._chunk, exception_on_overflow=False)
                if self._send_callback and data:
                    self._send_callback(data)
            except Exception:
                break
            time.sleep(0.001)

    def write_audio(self, data):
        if self._stream_out and self._running:
            try:
                self._stream_out.write(data)
            except Exception:
                pass

    def stop(self):
        self._running = False
        if self._stream_in:
            try:
                self._stream_in.stop_stream()
                self._stream_in.close()
            except Exception:
                pass
            self._stream_in = None
        if self._stream_out:
            try:
                self._stream_out.stop_stream()
                self._stream_out.close()
            except Exception:
                pass
            self._stream_out = None
