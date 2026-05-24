import threading
import time
import base64


class PhoneAudio:
    def __init__(self, client=None):
        self.client = client
        self._running = False
        self._capture_thread = None
        self._playback_thread = None
        self._on_audio = None

    def start_capture(self, on_audio_callback=None):
        self._on_audio = on_audio_callback
        self._running = True
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True
        )
        self._capture_thread.start()

    def _capture_loop(self):
        try:
            from jnius import autoclass

            AudioRecord = autoclass("android.media.AudioRecord")
            AudioSource = autoclass("android.media.MediaRecorder$AudioSource")
            AudioFormat = autoclass("android.media.AudioFormat")

            sample_rate = 16000
            channel_config = AudioFormat.CHANNEL_IN_MONO
            audio_format = AudioFormat.ENCODING_PCM_16BIT
            buffer_size = AudioRecord.getMinBufferSize(
                sample_rate, channel_config, audio_format
            )
            buffer_size = max(buffer_size, 3200)

            recorder = AudioRecord(
                AudioSource.MIC, sample_rate,
                channel_config, audio_format, buffer_size,
            )
            recorder.startRecording()

            buf = bytearray(3200)
            while self._running:
                n = recorder.read(buf, 0, len(buf))
                if n > 0:
                    chunk = bytes(buf[:n])
                    if self._on_audio:
                        self._on_audio(chunk)
                    elif self.client:
                        self.client.send_phone_audio(chunk)
                time.sleep(0.01)

            recorder.stop()
            recorder.release()
        except Exception:
            self._capture_fallback()

    def _capture_fallback(self):
        try:
            import pyaudio as pa
            p = pa.PyAudio()
            stream = p.open(
                format=pa.paInt16, channels=1, rate=16000,
                input=True, frames_per_buffer=3200,
            )
            while self._running:
                data = stream.read(3200, exception_on_overflow=False)
                if self.client:
                    self.client.send_phone_audio(data)
                time.sleep(0.01)
            stream.close()
            p.terminate()
        except Exception:
            pass

    def write_audio(self, pcm_bytes):
        try:
            from jnius import autoclass
            AudioTrack = autoclass("android.media.AudioTrack")
            AudioAttributes = autoclass("android.media.AudioAttributes")
            AudioFormat = autoclass("android.media.AudioFormat")

            attr_builder = AudioAttributes.Builder()
            attr_builder.setUsage(AudioAttributes.USAGE_MEDIA)
            attrs = attr_builder.build()

            fmt_builder = AudioFormat.Builder()
            fmt_builder.setEncoding(AudioFormat.ENCODING_PCM_16BIT)
            fmt_builder.setSampleRate(16000)
            fmt_builder.setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
            fmt = fmt_builder.build()

            track = AudioTrack.Builder()
            track.setAudioAttributes(attrs)
            track.setAudioFormat(fmt)
            track.setBufferSizeInBytes(6400)
            track.setTransferMode(AudioTrack.MODE_STREAM)
            track = track.build()
            track.play()
            track.write(pcm_bytes, 0, len(pcm_bytes))
        except Exception:
            self._play_fallback(pcm_bytes)

    def _play_fallback(self, pcm_bytes):
        try:
            import pyaudio as pa
            p = pa.PyAudio()
            stream = p.open(
                format=pa.paInt16, channels=1, rate=16000,
                output=True
            )
            stream.write(pcm_bytes)
            stream.close()
            p.terminate()
        except Exception:
            pass

    def stop(self):
        self._running = False
