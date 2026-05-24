import threading
import time
import struct


STATIONS = [
    {"name": "BBC Radio 1", "url": "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_one"},
    {"name": "BBC Radio 2", "url": "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_two"},
    {"name": "BBC Radio 3", "url": "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_three"},
    {"name": "BBC Radio 4", "url": "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_fourfm"},
    {"name": "Classic FM", "url": "http://icecast.thisisdax.com/ClassicFM"},
    {"name": "Absolute Radio", "url": "http://icecast.thisisdax.com/AbsoluteRadio"},
    {"name": "Capital FM", "url": "http://icecast.thisisdax.com/Capital"},
    {"name": "Heart Radio", "url": "http://icecast.thisisdax.com/Heart"},
    {"name": "Smooth Radio", "url": "http://icecast.thisisdax.com/Smooth"},
    {"name": "Jazz FM", "url": "http://icecast.thisisdax.com/JazzFMMusic"},
    {"name": "LBC", "url": "http://icecast.thisisdax.com/LBC"},
    {"name": "Radio X", "url": "http://icecast.thisisdax.com/RadioX"},
    {"name": "talkSPORT", "url": "http://radio.talksport.com/stream"},
    {"name": "Virgin Radio UK", "url": "http://icecast.thisisdax.com/VirginRadio"},
    {"type": "fm_separator", "name": "── FM Radio ──"},
    {"type": "fm", "name": "FM 88.0", "freq": 88.0},
    {"type": "fm", "name": "FM 88.5", "freq": 88.5},
    {"type": "fm", "name": "FM 89.1", "freq": 89.1},
    {"type": "fm", "name": "FM 89.5", "freq": 89.5},
    {"type": "fm", "name": "FM 90.3", "freq": 90.3},
    {"type": "fm", "name": "FM 91.1", "freq": 91.1},
    {"type": "fm", "name": "FM 92.1", "freq": 92.1},
    {"type": "fm", "name": "FM 93.1", "freq": 93.1},
    {"type": "fm", "name": "FM 94.1", "freq": 94.1},
    {"type": "fm", "name": "FM 95.1", "freq": 95.1},
    {"type": "fm", "name": "FM 96.1", "freq": 96.1},
    {"type": "fm", "name": "FM 97.1", "freq": 97.1},
    {"type": "fm", "name": "FM 98.1", "freq": 98.1},
    {"type": "fm", "name": "FM 99.1", "freq": 99.1},
    {"type": "fm", "name": "FM 100.1", "freq": 100.1},
    {"type": "fm", "name": "FM 101.1", "freq": 101.1},
    {"type": "fm", "name": "FM 102.1", "freq": 102.1},
    {"type": "fm", "name": "FM 103.1", "freq": 103.1},
    {"type": "fm", "name": "FM 104.1", "freq": 104.1},
    {"type": "fm", "name": "FM 105.1", "freq": 105.1},
    {"type": "fm", "name": "FM 106.1", "freq": 106.1},
    {"type": "fm", "name": "FM 107.1", "freq": 107.1},
    {"type": "fm", "name": "FM 107.9", "freq": 107.9},
]


class PhoneRadio:
    def __init__(self, client=None):
        self.client = client
        self._running = False
        self._radio_mgr = None
        self._radio_tuner = None
        self._audio_capture = None
        self._capture_thread = None
        self._playback_thread = None
        self._on_radio_audio = None
        self._current_freq = None
        self._current_station = None
        self._play_queue = []
        self._available = self._check_radio_api()

    def set_client(self, client):
        self.client = client

    def _check_radio_api(self):
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")
            context = PythonActivity.mActivity
            RadioManager = autoclass("android.hardware.radio.RadioManager")
            mgr = context.getSystemService(Context.RADIO_SERVICE)
            self._radio_mgr = mgr
            return mgr is not None
        except Exception:
            return False

    def has_fm_hardware(self):
        return self._available

    def get_stations(self):
        return STATIONS

    def start_fm_tuner(self, frequency_mhz, on_audio=None):
        self._on_radio_audio = on_audio
        self._current_freq = frequency_mhz
        self._running = True

        if self._available:
            return self._start_radio_api(frequency_mhz)
        return self._fallback_capture()

    def _start_radio_api(self, frequency_mhz):
        try:
            from jnius import autoclass, cast
            RadioManager = autoclass("android.hardware.radio.RadioManager")
            BandDescriptor = autoclass("android.hardware.radio.ProgramSelector$Identifier")
            ProgramSelector = autoclass("android.hardware.radio.ProgramSelector")

            modules = self._radio_mgr.listModules()
            if not modules or modules.size() == 0:
                return self._fallback_capture()

            module = modules.get(0)
            self._radio_tuner = self._radio_mgr.openTuner(
                module.getId(), None, True,  # callback, handler
            )
            freq_khz = int(frequency_mhz * 1000)
            self._radio_tuner.tune(freq_khz)

            self._capture_thread = threading.Thread(
                target=self._fm_capture_loop, daemon=True
            )
            self._capture_thread.start()
            return {"success": True, "method": "radio_api", "freq": frequency_mhz}
        except Exception as e:
            return self._fallback_capture()

    def _fm_capture_loop(self):
        try:
            from jnius import autoclass
            AudioRecord = autoclass("android.media.AudioRecord")
            AudioSource = autoclass("android.media.MediaRecorder$AudioSource")
            AudioFormat = autoclass("android.media.AudioFormat")

            audio_sources = [9, 7, 1]
            recorder = None
            for src in audio_sources:
                try:
                    sample_rate = 16000
                    ch = AudioFormat.CHANNEL_IN_MONO
                    fmt = AudioFormat.ENCODING_PCM_16BIT
                    buf_size = AudioRecord.getMinBufferSize(sample_rate, ch, fmt)
                    buf_size = max(buf_size, 3200)
                    recorder = AudioRecord(
                        src, sample_rate, ch, fmt, buf_size
                    )
                    recorder.startRecording()
                    if recorder.getRecordingState() == AudioRecord.RECORDSTATE_RECORDING:
                        break
                    recorder.release()
                    recorder = None
                except Exception:
                    if recorder:
                        recorder.release()
                    recorder = None

            if not recorder:
                return

            buf = bytearray(3200)
            while self._running:
                n = recorder.read(buf, 0, len(buf))
                if n > 0:
                    chunk = bytes(buf[:n])
                    if self._on_radio_audio:
                        self._on_radio_audio(chunk)
                    elif self.client:
                        self.client.send_phone_audio(chunk)
                time.sleep(0.01)

            recorder.stop()
            recorder.release()
        except Exception:
            pass

    def _fallback_capture(self):
        try:
            from jnius import autoclass
            AudioRecord = autoclass("android.media.AudioRecord")
            AudioSource = autoclass("android.media.MediaRecorder$AudioSource")
            AudioFormat = autoclass("android.media.AudioFormat")

            sample_rate = 16000
            ch = AudioFormat.CHANNEL_IN_MONO
            fmt = AudioFormat.ENCODING_PCM_16BIT
            buf_size = AudioRecord.getMinBufferSize(sample_rate, ch, fmt)
            buf_size = max(buf_size, 3200)

            recorder = AudioRecord(
                AudioSource.REMOTE_SUBMIX, sample_rate, ch, fmt, buf_size
            )
            recorder.startRecording()

            buf = bytearray(3200)
            while self._running:
                n = recorder.read(buf, 0, len(buf))
                if n > 0:
                    chunk = bytes(buf[:n])
                    if self._on_radio_audio:
                        self._on_radio_audio(chunk)
                    elif self.client:
                        self.client.send_phone_audio(chunk)
                time.sleep(0.01)

            recorder.stop()
            recorder.release()
        except Exception:
            pass

    def write_pc_radio_audio(self, pcm_bytes):
        try:
            from jnius import autoclass
            AudioTrack = autoclass("android.media.AudioTrack")
            AudioAttributes = autoclass("android.media.AudioAttributes")
            AudioFormat = autoclass("android.media.AudioFormat")

            attr = AudioAttributes.Builder()
            attr.setUsage(AudioAttributes.USAGE_MEDIA)
            attrs = attr.build()

            fmt = AudioFormat.Builder()
            fmt.setEncoding(AudioFormat.ENCODING_PCM_16BIT)
            fmt.setSampleRate(16000)
            fmt.setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
            afmt = fmt.build()

            track = AudioTrack.Builder()
            track.setAudioAttributes(attrs)
            track.setAudioFormat(afmt)
            track.setBufferSizeInBytes(6400)
            track.setTransferMode(AudioTrack.MODE_STREAM)
            track = track.build()
            track.play()
            track.write(pcm_bytes, 0, len(pcm_bytes))
        except Exception:
            pass

    def get_current(self):
        return {"frequency": self._current_freq, "station": self._current_station}

    def stop(self):
        self._running = False
        if self._radio_tuner:
            try:
                self._radio_tuner.close()
            except Exception:
                pass
            self._radio_tuner = None
