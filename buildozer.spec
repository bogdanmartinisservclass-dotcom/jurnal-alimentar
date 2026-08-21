[app]

title = Jurnal Alimentar
package.name = jurnalalimentar
package.domain = org.familia

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

requirements = python3==3.11.9,hostpython3==3.11.9,kivy,plyer

orientation = portrait
fullscreen = 0

android.permissions = READ_MEDIA_IMAGES,READ_EXTERNAL_STORAGE

android.api = 33
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
