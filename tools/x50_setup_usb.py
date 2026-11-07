#!/usr/bin/env python3
"""
x50_setup_usb.py - prepare everything to REMOVE the old SmartTube / NewPipe and
INSTALL the current SmartTube + NewPipe on a Proton X50 (ATLAS) head unit.

It downloads:
  * Ky Tang's "Uninstall SmartTube" scripts V1 and V2 (GitHub attachments)
  * the Custom App Script (Google Drive, linked from Install_Your_Own_Apps.md)
  * SmartTube and NewPipe from their official sources (via x50_get_apps.py)

and builds numbered folders. Each folder's CONTENT is what goes on the USB for
that step:

  1_UNINSTALL_SmartTube_V1
  2_UNINSTALL_SmartTube_V2_only_if_still_there
  3_UNINSTALL_custom_apps_only_if_NewPipe_still_there
  4_INSTALL_SmartTube_NewPipe

Usage:  python x50_setup_usb.py [--out X50_USB_STEPS]
Only the Python 3 standard library is used. Needs x50_get_apps.py and
x50_apk_prep.py next to it.
"""

from __future__ import annotations

import argparse
import io
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import x50_get_apps as getapps  # noqa: E402
import x50_apk_prep as prep  # noqa: E402

UNINSTALL_V1 = "https://github.com/user-attachments/files/32966943/uninstall.smart.tube.v1.zip"
UNINSTALL_V2 = "https://github.com/user-attachments/files/32966950/uinstall.smartube.v2.zip"
CUSTOM_APP_DRIVE_ID = "1EpvxZOyXnMC-YOJfu41RYuFS_HK6idGg"

STEP1 = "1_UNINSTALL_SmartTube_V1"
STEP2 = "2_UNINSTALL_SmartTube_V2_only_if_still_there"
STEP3 = "3_UNINSTALL_custom_apps_only_if_NewPipe_still_there"
STEP4 = "4_INSTALL_SmartTube_NewPipe"

HOW_TO = """HOW TO USE THESE FOLDERS  /  使用方法
=====================================

Each step = format the USB as FAT32 (32GB or smaller), copy the CONTENT of
that step's folder (not the folder itself) to the ROOT of the USB, start the
car, wait for the IHU to finish booting, plug the USB in and press nothing.
Wait until the IHU restarts. Unplug the USB.

每一步：USB Format 成 FAT32（32GB 或以下），把该步骤 Folder 里面的东西
（不是 Folder 本身）Copy 到 USB 根目录。启动汽车，等 IHU 开好，插 USB，
什么都不要按，等 IHU Restart，然后拔 USB。

STEP 1  {s1}
        Removes the old SmartTube. After the restart, check if SmartTube is gone.
        删除旧 SmartTube。Restart 后检查 SmartTube 是否已删除。

STEP 2  {s2}
        ONLY if SmartTube is still there after step 1.
        NEVER run it after step 4: it removes the new SmartTube too.
        只有在步骤 1 后 SmartTube 还在才做。
        步骤 4 之后绝对不要再跑，会把新的 SmartTube 也删掉。

STEP 3  {s3}
        ONLY if an old NewPipe icon is still there. This removes EVERY app that
        was installed with the Custom App Script (all hutroops.* apps), not just
        NewPipe. It also re-enables OTA updates.
        只有在旧 NewPipe 还在才做。会删除所有用 Custom App Script 装的 App
        （不只 NewPipe），也会重新开启 OTA 更新。

STEP 4  {s4}
        Installs SmartTube and NewPipe. The IHU may restart 2-3 times and
        "optimizing apps" can take 15-20 minutes. Do not turn the car off.
        It also DISABLES Proton OTA updates (com.malaysia.ota) and the car
        assistant app; step 3 turns them back on.
        安装 SmartTube 和 NewPipe。IHU 可能 Restart 2-3 次，优化 App 可能要
        15-20 分钟，不要熄火。也会关闭 Proton OTA 更新和 car assistant，
        步骤 3 可以重新开启。

AFTER: Hidden Settings > Sounds & Notification > App Notification >
       SmartTube / NewPipe > BLOCK.
       SmartTube login: Settings > Accounts > Add account, then open
       yt.be/activate on your phone and type the code.

To re-use a USB that already ran, the script folder is renamed to
"b832bc..._done". Rename it back (remove "_done") or copy the step again.
"""


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "x50-setup-usb"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def download_drive(file_id: str) -> bytes:
    """Download a public Google Drive file, handling the virus-scan page."""
    url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
    data = _get(url)
    if data[:2] == b"PK":
        return data
    html = data.decode("utf-8", "replace")
    uuid = re.search(r'name="uuid" value="([^"]+)"', html)
    if uuid:
        data = _get(url + f"&uuid={uuid.group(1)}")
        if data[:2] == b"PK":
            return data
    raise RuntimeError("Google Drive did not return a ZIP. Download it by hand from "
                       f"https://drive.google.com/file/d/{file_id}/view and pass --custom-app-zip.")


def find_script_root(root: Path) -> Optional[Path]:
    """The folder that directly contains a b832bc... script folder."""
    for d in sorted(root.rglob(prep.SCRIPT_FOLDER_PREFIX + "*"), key=lambda p: len(p.parts)):
        if d.is_dir() and "__MACOSX" not in d.parts:
            return d.parent
    return None


def extract_zip_step(data: bytes, dest: Path, label: str) -> None:
    tmp = dest.with_name(dest.name + "_tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(tmp)
    src = find_script_root(tmp)
    if src is None:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"{label}: no '{prep.SCRIPT_FOLDER_PREFIX}...' script folder inside the ZIP")
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(src, dest)
    shutil.rmtree(tmp, ignore_errors=True)


def find_dir_named(root: Path, name: str) -> Optional[Path]:
    for d in sorted(root.rglob(name), key=lambda p: len(p.parts)):
        if d.is_dir() and "__MACOSX" not in d.parts and find_script_root(d) == d:
            return d
    return None


def setup_custom_app(data: bytes, out: Path) -> None:
    tmp = out / "_custom_app_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(tmp)
    inst, uninst = find_dir_named(tmp, "install"), find_dir_named(tmp, "uninstall")
    if not inst or not uninst:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError("Custom App ZIP: 'install' / 'uninstall' folders with a b832bc... script not found")
    for src, step in ((uninst, STEP3), (inst, STEP4)):
        shutil.rmtree(out / step, ignore_errors=True)
        shutil.copytree(src, out / step)
    shutil.rmtree(tmp, ignore_errors=True)


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="X50_USB_STEPS", help="output folder (default X50_USB_STEPS)")
    ap.add_argument("--custom-app-zip", help="use an already downloaded 'Custom App.zip'")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    problems = 0

    for url, step, label in ((UNINSTALL_V1, STEP1, "Uninstall SmartTube V1"),
                             (UNINSTALL_V2, STEP2, "Uninstall SmartTube V2")):
        print(f"== {label}")
        try:
            extract_zip_step(_get(url), out / step, label)
            print(f"    ready: {out / step}")
        except Exception as exc:
            print(f"    !! {exc}")
            problems += 1

    print("== Custom App Script")
    try:
        data = Path(args.custom_app_zip).read_bytes() if args.custom_app_zip else download_drive(CUSTOM_APP_DRIVE_ID)
        setup_custom_app(data, out)
        print(f"    ready: {out / STEP3} and {out / STEP4}")
    except Exception as exc:
        print(f"    !! {exc}")
        print("    Install step skipped. Fix this first, then run again.")
        problems += 1
    else:
        app_dir = out / STEP4 / "app"
        rc = getapps.main(["--out", str(app_dir), "--overwrite", "smarttube", "newpipe"])
        problems += rc

    (out / "HOW_TO_USE.txt").write_text(
        HOW_TO.format(s1=STEP1, s2=STEP2, s3=STEP3, s4=STEP4), encoding="utf-8")
    print(f"\nInstructions: {out / 'HOW_TO_USE.txt'}")
    print("All ready." if not problems else f"Finished with {problems} problem(s) - see the !! lines above.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
