#!/usr/bin/env python3
"""
x50_apk_prep.py - helper for the Proton X50 (ATLAS) "Install Your Own Apps" script.

It automates the manual, error-prone steps 4-12 of Install_Your_Own_Apps.md
and adds a few safety checks for the USB drive.

Commands
--------
  info      Show package name, Android version requirements and native
            libraries of one or more APK files.
  prepare   Check APK files and lay them out the way the Custom App script
            expects:  <app folder>/hutroops.<package>/<package>.apk  plus
            lib/arm and lib/arm64 extracted and renamed from the APK.
  check-usb Check a USB drive before plugging it into the IHU (size, file
            system, script folder present, leftovers from macOS, "_done").
  reset-usb Rename the "..._done" script folder back so the USB can be
            reused (step 14 of the guide).

Only the Python 3 standard library is used (Python 3.9+), so it runs the
same on Windows, macOS and Linux. Nothing is ever written to the APK itself.

Examples
--------
  python x50_apk_prep.py info  Downloads/*.apk
  python x50_apk_prep.py prepare Downloads/*.apk --out "Custom App/install/app"
  python x50_apk_prep.py check-usb E:\\
  python x50_apk_prep.py reset-usb /Volumes/X50USB
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import struct
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# The ATLAS IHU runs Android 5.x (Lollipop). API 21 = 5.0, API 22 = 5.1.
IHU_MAX_SDK = 22
FOLDER_PREFIX = "hutroops."
SCRIPT_FOLDER_PREFIX = "b832bc"
DONE_SUFFIX = "_done"
USB_MAX_BYTES = 32 * 1000 ** 3  # "32GB" as printed on the drive
BUNDLE_EXTENSIONS = {".apks", ".xapk", ".apkm", ".aab"}

# Map of APK lib/<abi> folder -> folder name the IHU script expects.
# Order matters: the first ABI found for a target wins (v7a beats plain armeabi).
ABI_MAP = [
    ("armeabi-v7a", "arm"),
    ("armeabi", "arm"),
    ("arm64-v8a", "arm64"),
]

ANDROID_VERSIONS = {
    14: "4.0", 15: "4.0.3", 16: "4.1", 17: "4.2", 18: "4.3", 19: "4.4",
    21: "5.0", 22: "5.1", 23: "6.0", 24: "7.0", 25: "7.1", 26: "8.0",
    27: "8.1", 28: "9", 29: "10", 30: "11", 31: "12", 32: "12L", 33: "13",
    34: "14", 35: "15", 36: "16",
}


def android_name(sdk: Optional[int]) -> str:
    if sdk is None:
        return "unknown"
    return f"API {sdk} (Android {ANDROID_VERSIONS.get(sdk, '?')})"


# --------------------------------------------------------------------------
# Binary AndroidManifest.xml (AXML) parser - just enough to read the
# <manifest> and <uses-sdk> attributes.
# --------------------------------------------------------------------------

RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_RESOURCE_MAP_TYPE = 0x0180
UTF8_FLAG = 0x100
TYPE_STRING = 0x03
NO_INDEX = 0xFFFFFFFF

ATTR_IDS = {
    0x0101020C: "minSdkVersion",
    0x01010270: "targetSdkVersion",
    0x01010271: "maxSdkVersion",
    0x0101021B: "versionCode",
    0x0101021C: "versionName",
    0x01010591: "isSplitRequired",
}


class ManifestError(Exception):
    pass


def _read_string_pool(data: bytes, off: int) -> List[str]:
    _, header_size, _ = struct.unpack_from("<HHI", data, off)
    count, _styles, flags, strings_start, _ = struct.unpack_from("<IIIII", data, off + 8)
    offsets = struct.unpack_from(f"<{count}I", data, off + header_size)
    base = off + strings_start
    utf8 = bool(flags & UTF8_FLAG)
    out = []
    for o in offsets:
        p = base + o
        if utf8:
            # char length (skip), then byte length; each 1 or 2 bytes
            p += 2 if data[p] & 0x80 else 1
            n = data[p]
            if n & 0x80:
                n = ((n & 0x7F) << 8) | data[p + 1]
                p += 2
            else:
                p += 1
            out.append(data[p:p + n].decode("utf-8", errors="replace"))
        else:
            n = struct.unpack_from("<H", data, p)[0]
            p += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", data, p)[0]
                p += 2
            out.append(data[p:p + n * 2].decode("utf-16-le", errors="replace"))
    return out


def parse_manifest(data: bytes) -> Dict[str, Dict[str, object]]:
    """Return {element_name: {attr_name: value}} for manifest and uses-sdk."""
    if len(data) < 8 or struct.unpack_from("<H", data, 0)[0] != RES_XML_TYPE:
        raise ManifestError("AndroidManifest.xml is not in Android binary XML format")
    strings: List[str] = []
    res_ids: List[int] = []
    result: Dict[str, Dict[str, object]] = {}
    off = struct.unpack_from("<H", data, 2)[0]
    while off + 8 <= len(data):
        ctype, header_size, size = struct.unpack_from("<HHI", data, off)
        if size == 0:
            break
        if ctype == RES_STRING_POOL_TYPE:
            strings = _read_string_pool(data, off)
        elif ctype == RES_XML_RESOURCE_MAP_TYPE:
            n = (size - header_size) // 4
            res_ids = list(struct.unpack_from(f"<{n}I", data, off + header_size))
        elif ctype == RES_XML_START_ELEMENT_TYPE:
            ext = off + header_size
            _ns, name_i, attr_start, attr_size, attr_count = struct.unpack_from("<IIHHH", data, ext)
            tag = strings[name_i] if name_i < len(strings) else ""
            if tag in ("manifest", "uses-sdk", "application") and tag not in result:
                attrs: Dict[str, object] = {}
                for i in range(attr_count):
                    a = ext + attr_start + i * attr_size
                    _ans, aname, raw, _sz, _r0, dtype, value = struct.unpack_from("<IIIHBBI", data, a)
                    # Prefer resource id (survives obfuscated/empty attribute names)
                    key = ATTR_IDS.get(res_ids[aname]) if aname < len(res_ids) else None
                    if key is None:
                        key = strings[aname] if aname < len(strings) else f"attr{aname}"
                    if dtype == TYPE_STRING or raw != NO_INDEX:
                        attrs[key] = strings[raw] if raw < len(strings) else ""
                    else:
                        attrs[key] = value
                result[tag] = attrs
        off += size
    if "manifest" not in result:
        raise ManifestError("no <manifest> element found")
    return result


def _as_int(v: object) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    try:
        return int(str(v))
    except ValueError:
        return None  # codename preview SDK such as "Q"


# --------------------------------------------------------------------------
# APK inspection
# --------------------------------------------------------------------------

@dataclass
class ApkInfo:
    path: Path
    package: str = ""
    version_name: str = ""
    min_sdk: Optional[int] = None
    target_sdk: Optional[int] = None
    abis: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def inspect_apk(path: Path, max_sdk: int = IHU_MAX_SDK) -> ApkInfo:
    info = ApkInfo(path=path)
    if path.suffix.lower() in BUNDLE_EXTENSIONS:
        info.errors.append(
            f"'{path.suffix}' is a split APK / App Bundle. The IHU needs a single .apk file - "
            "download the plain APK variant instead.")
        return info
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        info.errors.append(f"not a valid APK/zip file ({e}). The download may be incomplete.")
        return info
    with zf:
        names = zf.namelist()
        apks_inside = [n for n in names if n.lower().endswith(".apk")]
        if "AndroidManifest.xml" not in names:
            if apks_inside:
                info.errors.append("this is a bundle of several APKs (split APK), not a single APK.")
            else:
                info.errors.append("AndroidManifest.xml missing - this is not an APK.")
            return info
        try:
            m = parse_manifest(zf.read("AndroidManifest.xml"))
        except (ManifestError, struct.error, IndexError) as e:
            info.errors.append(f"could not read AndroidManifest.xml: {e}")
            return info
        man = m["manifest"]
        sdk = m.get("uses-sdk", {})
        info.package = str(man.get("package", ""))
        info.version_name = str(man.get("versionName", ""))
        info.min_sdk = _as_int(sdk.get("minSdkVersion")) or 1
        info.target_sdk = _as_int(sdk.get("targetSdkVersion"))
        info.abis = sorted({n.split("/")[1] for n in names
                            if n.startswith("lib/") and n.count("/") >= 2 and n.endswith(".so")})

        if not info.package:
            info.errors.append("package name missing from manifest.")
        if man.get("split") or man.get("isSplitRequired") in (1, 0xFFFFFFFF, "true"):
            info.errors.append("this APK is one part of a split APK and cannot be installed alone.")
        if "minSdkVersion" in sdk and _as_int(sdk.get("minSdkVersion")) is None:
            info.errors.append(f"built for a preview Android version ({sdk.get('minSdkVersion')}).")
        elif info.min_sdk > max_sdk:
            info.errors.append(
                f"needs {android_name(info.min_sdk)} or newer, but the IHU runs Android 5.x "
                f"(API {max_sdk} max). Look for an older version of this app.")
        if info.abis and not any(a in info.abis for a, _ in ABI_MAP):
            info.errors.append(f"only contains native libraries for {', '.join(info.abis)} - no ARM build.")
        if info.abis and not any(a in info.abis for a in ("armeabi-v7a", "armeabi")):
            info.warnings.append("no 32-bit ARM libraries (armeabi*) - test the app carefully on the IHU.")
    return info


# --------------------------------------------------------------------------
# prepare
# --------------------------------------------------------------------------

def prepare_apk(info: ApkInfo, out_dir: Path, overwrite: bool = False) -> Path:
    dest = out_dir / f"{FOLDER_PREFIX}{info.package}"
    if dest.exists():
        if not overwrite:
            raise FileExistsError(f"{dest} already exists (use --overwrite to replace it)")
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copy2(info.path, dest / f"{info.package}.apk")

    with zipfile.ZipFile(info.path) as zf:
        done_targets = set()
        for abi, target in ABI_MAP:
            if target in done_targets or abi not in info.abis:
                continue
            done_targets.add(target)
            prefix = f"lib/{abi}/"
            for member in zf.infolist():
                if not member.filename.startswith(prefix) or member.is_dir():
                    continue
                rel = member.filename[len(prefix):]
                if not rel or ".." in Path(rel).parts:
                    continue
                target_path = dest / "lib" / target / rel
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    return dest


# --------------------------------------------------------------------------
# USB checks
# --------------------------------------------------------------------------

MACOS_JUNK = {".Spotlight-V100", ".fseventsd", ".Trashes", ".TemporaryItems", ".DS_Store"}


def detect_filesystem(path: Path) -> Optional[str]:
    """Best-effort file system name of the volume holding `path`."""
    try:
        system = platform.system()
        if system == "Windows":
            import ctypes
            root = os.path.splitdrive(str(path.resolve()))[0] + "\\"
            buf = ctypes.create_unicode_buffer(64)
            ok = ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(root), None, 0, None, None, None, buf, len(buf))
            return buf.value if ok else None
        if system == "Linux":
            best, fs = "", None
            real = str(path.resolve())
            with open("/proc/mounts") as f:
                for line in f:
                    parts = line.split()
                    mnt = parts[1].replace("\\040", " ")
                    if (real == mnt or real.startswith(mnt.rstrip("/") + "/")) and len(mnt) > len(best):
                        best, fs = mnt, parts[2]
            return fs
        if system == "Darwin":
            out = subprocess.run(["diskutil", "info", str(path)], capture_output=True, text=True).stdout
            for line in out.splitlines():
                if "File System Personality" in line or "Type (Bundle)" in line:
                    return line.split(":", 1)[1].strip()
    except Exception:
        return None
    return None


def check_usb(root: Path) -> int:
    problems, notes = [], []
    if not root.is_dir():
        print(f"ERROR: {root} is not a folder / drive")
        return 2

    total = shutil.disk_usage(root).total
    if total > USB_MAX_BYTES * 1.05:
        problems.append(f"drive is {total / 1e9:.0f} GB - the IHU only reliably reads drives of 32 GB or smaller.")

    fs = detect_filesystem(root)
    if fs is None:
        notes.append("could not detect the file system - make sure it is FAT32.")
    elif fs.lower() not in ("vfat", "fat32", "msdos", "ms-dos fat32", "fat"):
        problems.append(f"file system is '{fs}', but it must be FAT32 (exFAT/NTFS/APFS will not work).")

    entries = list(root.iterdir())
    script = [e for e in entries if e.is_dir() and e.name.startswith(SCRIPT_FOLDER_PREFIX)]
    done = [e for e in script if e.name.endswith(DONE_SUFFIX)]
    if not script:
        problems.append(f"no '{SCRIPT_FOLDER_PREFIX}...' script folder in the root of the drive. "
                        "Copy the extracted folders to the root, not inside another folder.")
    for d in done:
        problems.append(f"'{d.name}' was already run. Run 'reset-usb' to reuse it, or copy a fresh script.")
    nested = [e for e in entries if e.is_dir() and not e.name.startswith((SCRIPT_FOLDER_PREFIX, "."))
              and e.name not in ("app", "System Volume Information")
              and any(c.name.startswith(SCRIPT_FOLDER_PREFIX) for c in e.iterdir() if c.is_dir())]
    for n in nested:
        problems.append(f"script folder found inside '{n.name}/' - move its contents to the drive root.")

    app = root / "app"
    if app.is_dir():
        for d in sorted(app.iterdir()):
            if d.is_dir() and d.name.startswith(FOLDER_PREFIX):
                pkg = d.name[len(FOLDER_PREFIX):]
                if not (d / f"{pkg}.apk").is_file():
                    problems.append(f"app/{d.name}/ should contain '{pkg}.apk'.")
                lib = d / "lib"
                if lib.is_dir():
                    bad = [x.name for x in lib.iterdir() if x.name not in ("arm", "arm64")]
                    if bad:
                        problems.append(f"app/{d.name}/lib/ has {', '.join(bad)} - only 'arm' and 'arm64' are allowed.")

    junk = [e.name for e in entries if e.name in MACOS_JUNK]
    junk += [str(p.relative_to(root)) for p in root.rglob("._*")][:20]
    if junk:
        notes.append("macOS metadata files found (" + ", ".join(junk[:5]) +
                     (", ..." if len(junk) > 5 else "") + "). Run with --clean-macos to remove them.")

    for p in problems:
        print(f"PROBLEM: {p}")
    for n in notes:
        print(f"NOTE:    {n}")
    if not problems:
        print("OK: USB drive looks ready. Plug it into the IHU after it has fully booted.")
    return 1 if problems else 0


def clean_macos(root: Path) -> None:
    for e in root.iterdir():
        if e.name in MACOS_JUNK:
            shutil.rmtree(e, ignore_errors=True) if e.is_dir() else e.unlink()
            print(f"removed {e}")
    for p in list(root.rglob("._*")):
        if p.is_file():
            p.unlink()
            print(f"removed {p}")


def reset_usb(root: Path) -> int:
    done = [e for e in root.iterdir() if e.is_dir()
            and e.name.startswith(SCRIPT_FOLDER_PREFIX) and e.name.endswith(DONE_SUFFIX)]
    if not done:
        print("Nothing to reset - no '..._done' script folder found.")
        return 0
    rc = 0
    for d in done:
        new = d.with_name(d.name[: -len(DONE_SUFFIX)])
        if new.exists():
            print(f"SKIP: {new.name} already exists next to {d.name}")
            rc = 1
            continue
        d.rename(new)
        print(f"renamed {d.name} -> {new.name}")
    return rc


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _print_info(info: ApkInfo) -> None:
    print(f"\n{info.path.name}")
    if info.package:
        print(f"  package     : {info.package}")
        print(f"  version     : {info.version_name or '?'}")
        print(f"  min Android : {android_name(info.min_sdk)}")
        print(f"  target      : {android_name(info.target_sdk)}")
        print(f"  native libs : {', '.join(info.abis) if info.abis else 'none'}")
    for w in info.warnings:
        print(f"  WARNING: {w}")
    for e in info.errors:
        print(f"  ERROR: {e}")
    print("  => " + ("compatible" if info.ok else "NOT compatible with the X50 IHU"))


def _expand(paths: List[str]) -> List[Path]:
    out: List[Path] = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            out += sorted(x for x in pp.iterdir() if x.suffix.lower() in BUNDLE_EXTENSIONS | {".apk"})
        elif any(c in p for c in "*?["):  # Windows shells do not expand globs
            out += sorted(Path().glob(p))
        else:
            out.append(pp)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("Commands")[0].strip(),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_info = sub.add_parser("info", help="show APK details and compatibility")
    p_info.add_argument("apks", nargs="+", help="APK files or folders containing APKs")
    p_info.add_argument("--max-sdk", type=int, default=IHU_MAX_SDK, help=argparse.SUPPRESS)

    p_prep = sub.add_parser("prepare", help="lay out APKs for the Custom App script")
    p_prep.add_argument("apks", nargs="+", help="APK files or folders containing APKs")
    p_prep.add_argument("--out", required=True, help='the "Custom App/install/app" folder (or app/ on the USB)')
    p_prep.add_argument("--overwrite", action="store_true", help="replace an existing hutroops.<pkg> folder")
    p_prep.add_argument("--force", action="store_true", help="prepare even APKs that fail the checks")
    p_prep.add_argument("--max-sdk", type=int, default=IHU_MAX_SDK, help=argparse.SUPPRESS)

    p_chk = sub.add_parser("check-usb", help="check a USB drive before using it in the car")
    p_chk.add_argument("usb", help="root of the USB drive, e.g. E:\\ or /Volumes/USB")
    p_chk.add_argument("--clean-macos", action="store_true", help="delete ._* and other macOS files first")

    p_rst = sub.add_parser("reset-usb", help="rename the '_done' script folder so the USB can be reused")
    p_rst.add_argument("usb", help="root of the USB drive")

    args = ap.parse_args(argv)

    if args.cmd == "info":
        infos = [inspect_apk(p, args.max_sdk) for p in _expand(args.apks)]
        for i in infos:
            _print_info(i)
        return 0 if infos and all(i.ok for i in infos) else 1

    if args.cmd == "prepare":
        out = Path(args.out)
        apks = _expand(args.apks)
        if not apks:
            print("No APK files given.")
            return 2
        failed = 0
        seen: Dict[str, Path] = {}
        for p in apks:
            info = inspect_apk(p, args.max_sdk)
            _print_info(info)
            if not info.ok and not (args.force and info.package):
                print("  -> skipped")
                failed += 1
                continue
            if info.package in seen:
                print(f"  -> skipped: same package as {seen[info.package].name}")
                failed += 1
                continue
            try:
                dest = prepare_apk(info, out, args.overwrite)
            except FileExistsError as e:
                print(f"  -> skipped: {e}")
                failed += 1
                continue
            seen[info.package] = p
            libs = sorted(x.name for x in (dest / "lib").iterdir()) if (dest / "lib").is_dir() else []
            print(f"  -> {dest}" + (f"  (lib: {', '.join(libs)})" if libs else ""))
        print(f"\nPrepared {len(seen)} app(s), skipped {failed}.")
        return 1 if failed else 0

    root = Path(args.usb)
    if args.cmd == "check-usb":
        if args.clean_macos and root.is_dir():
            clean_macos(root)
        return check_usb(root)
    if args.cmd == "reset-usb":
        return reset_usb(root)
    return 2


if __name__ == "__main__":
    sys.exit(main())
