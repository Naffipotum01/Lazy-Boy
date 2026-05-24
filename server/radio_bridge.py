import threading
import subprocess
import json
import os
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
    {"name": "Kisstory", "url": "http://icecast.thisisdax.com/Kisstory"},
    {"name": "Radio X", "url": "http://icecast.thisisdax.com/RadioX"},
    {"name": "Planet Rock", "url": "http://icecast.thisisdax.com/PlanetRock"},
    {"name": "talkSPORT", "url": "http://radio.talksport.com/stream"},
    {"name": "Virgin Radio UK", "url": "http://icecast.thisisdax.com/VirginRadio"},
]


class PcRadioTuner:
    def __init__(self):
        self._process = None
        self._thread = None
        self._running = False
        self._send_callback = None
        self._current_station = None
        self._ffmpeg_checked = False
        self._ffmpeg_available = False

    def set_send_callback(self, cb):
        self._send_callback = cb

    def get_stations(self):
        return STATIONS

    def _check_ffmpeg(self):
        if self._ffmpeg_checked:
            return self._ffmpeg_available
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True, timeout=5
            )
            self._ffmpeg_available = True
        except Exception:
            self._ffmpeg_available = False
        self._ffmpeg_checked = True
        return self._ffmpeg_available

    def tune(self, station_name_or_url):
        self.stop()
        url = None
        name = station_name_or_url
        for s in STATIONS:
            if s["name"].lower() == station_name_or_url.lower() or s["url"] == station_name_or_url:
                url = s["url"]
                name = s["name"]
                break
        if not url:
            if station_name_or_url.startswith("http"):
                url = station_name_or_url
                name = "Custom"
            else:
                return {"success": False, "error": f"Station '{station_name_or_url}' not found"}

        if not self._check_ffmpeg():
            return {"success": False, "error": "ffmpeg not found. Install ffmpeg or use the direct URL player."}

        self._current_station = {"name": name, "url": url}
        self._running = True
        self._thread = threading.Thread(
            target=self._stream_loop, args=(url,), daemon=True
        )
        self._thread.start()
        return {"success": True, "station": name, "method": "ffmpeg"}

    def play_url_direct(self, url):
        self.stop()
        self._running = True
        self._current_station = {"name": url, "url": url}
        self._thread = threading.Thread(
            target=self._stream_loop, args=(url,), daemon=True
        )
        self._thread.start()
        return {"success": True}

    def _stream_loop(self, url):
        try:
            cmd = [
                "ffmpeg", "-v", "quiet",
                "-i", url,
                "-f", "s16le",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                "-"
            ]
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                bufsize=4096
            )
            while self._running and self._process.poll() is None:
                data = self._process.stdout.read(4096)
                if not data:
                    break
                if self._send_callback:
                    self._send_callback(data)
                time.sleep(0.001)
        except Exception:
            pass
        finally:
            if self._process:
                try:
                    self._process.kill()
                except Exception:
                    pass
                self._process = None
            self._running = False

    def get_current(self):
        return self._current_station

    def scan_frequencies(self, callback=None):
        results = []
        for freq in range(875, 1081, 2):
            freq_mhz = freq / 10.0
            results.append({
                "frequency": f"{freq_mhz:.1f}",
                "name": f"FM {freq_mhz:.1f}",
                "type": "fm",
            })
        if callback:
            callback(results)
        return results

    def stop(self):
        self._running = False
        if self._process:
            try:
                self._process.kill()
            except Exception:
                pass
            try:
                self._process.wait(3)
            except Exception:
                pass
            self._process = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._current_station = None
