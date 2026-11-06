# X50 APK prep tool

`x50_apk_prep.py` does the fiddly parts of [Install Your Own Apps](../Install_Your_Own_Apps.md) for you, and checks your USB drive before you walk to the car.

| Command | What it does |
|---|---|
| `info` | Shows each APK's package name, minimum Android version and native libraries, and says whether it can run on the IHU (Android 5.x). |
| `prepare` | Checks each APK, then creates `hutroops.<package>/<package>.apk` and copies `lib/armeabi*` to `lib/arm` and `lib/arm64-v8a` to `lib/arm64`. Unsupported folders such as `x86` are left out. This replaces steps 4 to 12 of the guide. |
| `check-usb` | Checks the USB drive: 32 GB or smaller, FAT32, script folder in the root, no `_done` folder, app folders laid out correctly, no hidden macOS files. |
| `reset-usb` | Renames `b832bc..._done` back to `b832bc...` so you can run the same USB again (step 14 of the guide). |

It never changes your APK files. It only copies them.

## 1. Install Python (one time)

- **Windows:** install Python 3 from [python.org](https://www.python.org/downloads/) and tick **"Add python.exe to PATH"** in the installer.
- **macOS / Linux:** Python 3 is usually already installed. Use `python3` where this page says `python`.

Then download [`x50_apk_prep.py`](x50_apk_prep.py) (open it, then click the download button) and put it in the same folder as your APKs, or anywhere you like.

## 2. Check your APKs

Open a terminal in that folder (Windows: type `cmd` in the File Explorer address bar and press Enter), then run:

```
python x50_apk_prep.py info .
```

`.` means "every APK in this folder". You can also name files: `python x50_apk_prep.py info spotify.apk waze.apk`.

Example output:

```
smarttube_stable.apk
  package     : org.smarttube.stable
  version     : 32.71
  min Android : API 17 (Android 4.2)
  target      : API 34 (Android 14)
  native libs : arm64-v8a, armeabi-v7a
  => compatible
```

If an app says **NOT compatible**, the reason is printed above it. Usually you need an older version of the app, or the single-APK download instead of an XAPK/APKS bundle.

## 3. Prepare the Custom App folder

Unzip the Custom App script (link in [the guide](../Install_Your_Own_Apps.md)), then:

```
python x50_apk_prep.py prepare . --out "Custom App/install/app"
```

Each compatible APK gets its own `hutroops.<package>` folder in `install/app`. Incompatible APKs are skipped and the reason is shown. Add `--overwrite` to replace a folder you prepared before.

Copy the **contents** of `Custom App/install` to the root of your FAT32 USB drive, as in step 13 of the guide.

## 4. Check the USB drive

```
python x50_apk_prep.py check-usb E:\
```

Use your USB drive letter on Windows, `/Volumes/<name>` on macOS, or the mount point on Linux. On a Mac, add `--clean-macos` to delete the hidden `._*` files that macOS writes to USB drives.

## 5. Reuse a USB drive

After a run, the script renames its folder to `..._done` so it doesn't run twice. To run it again:

```
python x50_apk_prep.py reset-usb E:\
```

## For developers

The tool only uses the Python standard library. Tests: `python -m unittest discover tools`.
