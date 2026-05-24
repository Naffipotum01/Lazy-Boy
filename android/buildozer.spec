[app]

title = Lazy Boy
package.name = lazyboy
package.domain = com.lazyboy
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0

requirements = python3,kivy,websocket-client,pillow

orientation = sensor
fullscreen = 1
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE
android.api = 34
android.minapi = 24
android.ndk = 26b
android.archs = arm64-v8a

services = LBService:service.py:foreground

icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png

[buildozer]
log_level = 2
warn_on_root = 0
