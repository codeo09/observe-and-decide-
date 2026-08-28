[app]
title = Agency
package.name = agencygame
package.domain = org.yourname
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3==3.11.8,kivy==2.3.0,kivymd==1.2.0,pyjnius==1.6.1
orientation = portrait
fullscreen = 0

# (Android specific)
android.permissions =
android.api = 33
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
