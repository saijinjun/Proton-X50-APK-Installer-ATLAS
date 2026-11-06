# Troubleshooting / 问题排查

Work through the checks in order. Most problems come from the USB drive.  
请按顺序检查。大部分问题都来自 Pendrive。

> Tip: the [X50 APK prep tool](tools/README.md) can run most of the USB checks below for you: `python x50_apk_prep.py check-usb E:\`

## Nothing happens when I plug in the USB / 插入 Pendrive 后没有反应

1. **Drive size.** Use a USB drive of **32 GB or smaller**. Larger drives are often not read.  
   **Pendrive 大小**：请使用 **32GB 或以下** 的 Pendrive。
2. **File system.** Format it as **FAT32** with an **MBR** partition table. exFAT, NTFS, APFS and Mac OS Extended will not work. Windows only offers FAT32 for drives up to 32 GB, which is another reason to use a small drive.  
   **格式**：必须 Format 成 **FAT32**（MBR）。exFAT / NTFS 无法使用。
3. **Folder in the root.** The `b832bc...` folder (and `app` if there is one) must be in the **root** of the drive, not inside another folder such as `Custom App/` or `latest newpipe/`.  
   **Folder 位置**：`b832bc...` 和 `app` Folder 必须放在 Pendrive 的最外层。
4. **Already run.** If the folder is now called `b832bc..._done`, the script already ran on this drive. Remove `_done` from the name, or copy a fresh copy from the ZIP.  
   **已运行过**：如果 Folder 名字变成 `..._done`，请把 `_done` 删掉或者重新 Copy。
5. **Wait for the IHU to boot fully.** Start the car, wait until the home screen is ready, then plug in the USB drive.  
   **等 IHU 完全启动** 后再插入 Pendrive。
6. **Try the other USB port** or another USB drive. Some cheap or very fast drives are not detected.

## I use a Mac / 我用 Mac

macOS writes hidden files (`._*`, `.Spotlight-V100`, `.fseventsd`, `.Trashes`) to every USB drive, and these can stop the script. Format the drive in Disk Utility as **MS-DOS (FAT)** with the **Master Boot Record** scheme. After copying the files, run `python3 x50_apk_prep.py check-usb /Volumes/<name> --clean-macos`, or remove the hidden files with `dot_clean /Volumes/<name>` in Terminal, then eject the drive properly.  
See also [issue #5](https://github.com/xeon1989/Proton-X50-APK-Installer-ATLAS/issues/5).

## The script ran but apps are not installed / Script 运行了但 App 没有安装

- **Firmware.** Installing apps only works on ATLAS **617 / 618** firmware from before 2 March 2023. Later updates blocked it. See the [archived notice](%5BArchived%5D%20Notice.md) for how to flash 617v1 / 618v1.
- **Be patient.** After the restart the IHU "optimises apps" for up to 15 to 20 minutes. Do not switch off the car during that time.
- **NewPipe / SmartTube installers** restart the IHU 2 to 3 times: first to remove the old version, then to install the new one. Wait until the installer no longer starts by itself.
- **Mixed install methods.** If apps were installed some other way, the standard install and uninstall scripts are not compatible. See *Important Notes* in the [README](README.md).

## A custom app does not install or crashes / 自己的 App 无法安装或闪退

Run `python x50_apk_prep.py info your.apk` (see [the tool guide](tools/README.md)). The usual reasons are:

| Reason | Fix |
|---|---|
| The app needs Android 6.0 or newer (minSdk > 22) | Download an older version of the app that supports Android 5.0 / 5.1. |
| It is a split APK / XAPK / APKS / App Bundle | Download the single `.apk` variant. |
| Native libraries only for x86 | Find an ARM (`armeabi-v7a`) build. |
| The folder or APK name does not match the package name | Use `prepare`, which names everything for you. |
| `lib` folder not renamed to `arm` / `arm64` | Use `prepare`, or follow step 11 of the [guide](Install_Your_Own_Apps.md). |

Some apps still need Google Play Services or newer system components and will not run on the IHU even when all checks pass.

## Notifications pop up over the screen / 通知一直弹出

Go to **Hidden Settings → Sounds & Notification → App Notification → (app) → BLOCK**. Do this for Android Auto, Spotify, NewPipe, SmartTube and any other app whose notifications you do not need. See [Recommended Settings](RecommendedSettings.md).

## Steering wheel buttons do not work in Android Auto / CarPlay

See the [steering button workaround](SteeringButtonWorkaroundAA.md), or use Autokit 2023.12.25.1107 or newer with a Carlinkit dongle.

## The IHU is slow / IHU 很慢

Disable apps you don't use with the scripts in [Optimization](Optimization.md). Disabling Proton Maps helps the most.

## Still stuck? / 还是不行？

Open a post in [Issues](https://github.com/xeon1989/Proton-X50-APK-Installer-ATLAS/issues) and include:

- your ATLAS firmware version,
- which script or ZIP you used,
- USB drive size and file system,
- what the screen showed, and how many times the IHU restarted.
