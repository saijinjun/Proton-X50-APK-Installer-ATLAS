#!/usr/bin/env python3
"""
x50_get_apps.py - download entertainment / music apps from their OFFICIAL
sources and lay them out for the Proton X50 (ATLAS) Custom App script.

Apps (all work without Google Play Services):
  smarttube  YouTube with Google account login (official GitHub, stable, armeabi-v7a)
  newpipe    YouTube / music with background play, no login (official GitHub)
  vlc        Local music/video from USB + internet radio streams (videolan.org)
  headunit   Open Headunit: Android Auto from your phone over USB (official GitHub)
  radiodroid Internet radio, thousands of stations (F-Droid)
  vinyl      Simple offline music player for USB / local files (F-Droid)

For each app the newest release is tried first. If it needs a newer Android
than the IHU (5.1 / API 22), older releases are tried until one fits
(up to --tries releases; not for VLC).

Usage
-----
  python x50_get_apps.py --out "Custom App/install/app"            # all apps
  python x50_get_apps.py --out "Custom App/install/app" smarttube vlc

Downloads are kept in ./x50_downloads. Then copy the content of the
"Custom App/install" folder to a FAT32 USB drive (see Install_Your_Own_Apps.md).

Only the Python 3 standard library is used. Needs x50_apk_prep.py next to it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import x50_apk_prep as prep  # noqa: E402

UA = {"User-Agent": "x50-get-apps", "Accept": "application/vnd.github+json"}
DL_DIR = Path("x50_downloads")

Candidate = Tuple[str, str, Optional[str]]  # (version, url, sha256 url)


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _github_releases(repo: str) -> List[dict]:
    return json.loads(_get(f"https://api.github.com/repos/{repo}/releases?per_page=30"))


def pick_smarttube_asset(names: List[str]) -> Optional[str]:
    """Prefer the stable armeabi-v7a build (runs on 32- and 64-bit ARM)."""
    apks = [n for n in names if n.lower().endswith(".apk")]
    for want in (("stable", "armeabi-v7a"), ("armeabi-v7a",), ("stable", "universal"), ("stable",)):
        for n in apks:
            low = n.lower()
            if all(w in low for w in want) and "x86" not in low:
                return n
    return None


def pick_newpipe_asset(names: List[str]) -> Optional[str]:
    apks = [n for n in names if n.lower().endswith(".apk") and "x86" not in n.lower()]
    return apks[0] if apks else None


def github_candidates(repo: str, picker: Callable[[List[str]], Optional[str]]) -> Iterator[Candidate]:
    for rel in _github_releases(repo):
        if rel.get("prerelease") or rel.get("draft"):
            continue
        assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
        name = picker(list(assets))
        if name:
            yield rel["tag_name"], assets[name], None


def pick_any_apk(names: List[str]) -> Optional[str]:
    """First ARM/universal APK, preferring release over debug builds."""
    apks = [n for n in names if n.lower().endswith(".apk") and "x86" not in n.lower()]
    apks.sort(key=lambda n: "debug" in n.lower())
    return apks[0] if apks else None


def fdroid_candidates(package: str) -> Iterator[Candidate]:
    """Newest first, from the official F-Droid repository."""
    meta = json.loads(_get(f"https://f-droid.org/api/v1/packages/{package}"))
    for p in sorted(meta.get("packages", []), key=lambda p: p["versionCode"], reverse=True):
        yield p.get("versionName", str(p["versionCode"])), \
            f"https://f-droid.org/repo/{package}_{p['versionCode']}.apk", None


def vlc_candidates() -> Iterator[Candidate]:
    base = "https://get.videolan.org/vlc-android/last/"
    html = _get(base).decode("utf-8", "replace")
    names = sorted(set(re.findall(r'href="(VLC-Android-[^"]*armeabi-v7a\.apk)"', html)))
    for n in names:
        ver = n.split("-")[2] if n.count("-") >= 3 else "last"
        yield ver, base + n, base + n + ".sha256"


APPS: Dict[str, Callable[[], Iterator[Candidate]]] = {
    "smarttube": lambda: github_candidates("yuliskov/SmartTube", pick_smarttube_asset),
    "newpipe": lambda: github_candidates("TeamNewPipe/NewPipe", pick_newpipe_asset),
    "vlc": vlc_candidates,
    "headunit": lambda: github_candidates("andreknieriem/headunit-revived", pick_any_apk),
    "radiodroid": lambda: fdroid_candidates("net.programmierecke.radiodroid2"),
    "vinyl": lambda: fdroid_candidates("com.poupa.vinylmusicplayer"),
}


def download(url: str, sha_url: Optional[str]) -> Path:
    DL_DIR.mkdir(exist_ok=True)
    dest = DL_DIR / url.rsplit("/", 1)[-1]
    if not dest.exists():
        print(f"    downloading {url}")
        data = _get(url)
        if sha_url:
            expected = _get(sha_url).decode().split()[0].lower()
            actual = hashlib.sha256(data).hexdigest()
            if expected != actual:
                raise RuntimeError(f"SHA-256 mismatch for {dest.name}")
            print("    SHA-256 verified")
        dest.write_bytes(data)
    return dest


def fetch_app(app: str, tries: int) -> Optional[prep.ApkInfo]:
    print(f"\n== {app}")
    for i, (ver, url, sha) in enumerate(APPS[app]()):
        if i >= tries:
            break
        apk = download(url, sha)
        info = prep.inspect_apk(apk)
        print(f"    {ver}: {info.package or '?'} needs {prep.android_name(info.min_sdk)}")
        if info.ok:
            return info
        for e in info.errors:
            print(f"    - {e}")
        print("    trying an older release...")
    print(f"    !! no release of {app} that runs on Android 5.1 was found")
    return None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("apps", nargs="*", help=f"apps to get: {', '.join(APPS)} (default: all)")
    ap.add_argument("--out", required=True, help='the "Custom App/install/app" folder')
    ap.add_argument("--tries", type=int, default=5, help="max releases to try per app (default 5)")
    ap.add_argument("--overwrite", action="store_true", help="replace existing hutroops.<pkg> folders")
    args = ap.parse_args(argv)
    unknown = [a for a in args.apps if a not in APPS]
    if unknown:
        ap.error(f"unknown app(s): {', '.join(unknown)}. Choose from: {', '.join(APPS)}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for app in args.apps or list(APPS):
        try:
            info = fetch_app(app, args.tries)
        except Exception as exc:  # network / API errors
            print(f"    !! {app}: {exc}")
            info = None
        if info is None:
            failed += 1
            continue
        dest = prep.prepare_apk(info, out, overwrite=args.overwrite)
        print(f"    ready: {dest}")
    print("\nDone." if not failed else f"\nDone with {failed} problem(s).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
