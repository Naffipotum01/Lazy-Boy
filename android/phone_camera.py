import threading
import time
import base64


class PhoneCameraStreamer:
    def __init__(self, client=None):
        self.client = client
        self._running = False
        self._thread = None

    def start(self, facing="back"):
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop, args=(facing,), daemon=True
        )
        self._thread.start()

    def _capture_loop(self, facing):
        try:
            from jnius import autoclass

            Camera = autoclass("android.hardware.Camera")
            CameraInfo = autoclass("android.hardware.Camera$CameraInfo")
            Parameters = autoclass("android.hardware.Camera$Parameters")
            JavaSurface = autoclass("android.view.Surface")
            Bitmap = autoclass("android.graphics.Bitmap")
            ByteArrayOutputStream = autoclass("java.io.ByteArrayOutputStream")

            camera_id = 0
            info = CameraInfo()
            for i in range(Camera.getNumberOfCameras()):
                Camera.getCameraInfo(i, info)
                if facing == "front" and info.facing == CameraInfo.CAMERA_FACING_FRONT:
                    camera_id = i
                    break
                elif facing == "back" and info.facing == CameraInfo.CAMERA_FACING_BACK:
                    camera_id = i
                    break

            cam = Camera.open(camera_id)
            params = cam.getParameters()
            available = params.getSupportedPictureSizes()
            if available and available.size() > 0:
                size = available.get(available.size() - 1)
                params.setPictureSize(size.width, size.height)
            cam.setParameters(params)

            buffer_size = 320 * 1024

            class PreviewCallback:
                def onPreviewFrame(self, yuv_data, camera):
                    pass

            callback = PreviewCallback()
            cam.setPreviewCallback(callback)
            cam.startPreview()

            while self._running:
                cam.takePicture(None, None, lambda data, cam: None)
                time.sleep(0.1)
                try:
                    cam.startPreview()
                except Exception:
                    pass
                time.sleep(0.8)

            cam.stopPreview()
            cam.release()

        except Exception:
            self._capture_fallback(facing)

    def _capture_fallback(self, facing):
        try:
            from kivy.core.camera import Camera as KivyCamera
            from kivy.clock import Clock
            import io

            cam_id = 1 if facing == "front" else 0
            cam = None

            def on_frame(dt):
                nonlocal cam
                if not self._running:
                    return
                try:
                    if cam is None:
                        cam = KivyCamera(cam_id, resolution=(640, 480))
                        cam.play = True
                    if cam.texture:
                        from kivy.graphics.texture import Texture
                        tex = cam.texture
                        w, h = tex.width, tex.height
                        buf = tex.pixels
                        from PIL import Image
                        img = Image.frombuffer("RGBA", (w, h), buf, "raw", "RGBA", 0, 1)
                        rgb = img.convert("RGB")
                        out = io.BytesIO()
                        rgb.save(out, format="JPEG", quality=50)
                        jpg = out.getvalue()
                        if self.client and self.client.connected:
                            self.client.send_phone_camera(jpg)
                except Exception:
                    pass

            ev = Clock.schedule_interval(on_frame, 0.15)
            while self._running:
                time.sleep(0.1)
            if cam:
                cam.play = False
                cam = None
            Clock.unschedule(ev)
        except Exception:
            pass

    def stop(self):
        self._running = False
