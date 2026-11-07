"""Tests for x50_apk_prep.py.  Run:  python -m unittest discover tools"""

import io
import struct
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import x50_apk_prep as t  # noqa: E402

ANDROID_NS = "http://schemas.android.com/apk/res/android"
RES_IDS = {"minSdkVersion": 0x0101020C, "targetSdkVersion": 0x01010270, "versionName": 0x0101021C}


def make_axml(package, min_sdk=None, target_sdk=None, version="1.0", utf8=True, split=None):
    """Build a minimal binary AndroidManifest.xml."""
    strings = ["minSdkVersion", "targetSdkVersion", "versionName", "android", ANDROID_NS,
               "package", "manifest", "uses-sdk", "split", package, version]
    if split:
        strings.append(split)
    idx = {s: i for i, s in enumerate(strings)}

    # string pool
    data = b""
    offsets = []
    for s in strings:
        offsets.append(len(data))
        if utf8:
            b = s.encode()
            data += bytes([len(s), len(b)]) + b + b"\0"
        else:
            data += struct.pack("<H", len(s)) + s.encode("utf-16-le") + b"\0\0"
    data += b"\0" * (-len(data) % 4)
    hdr = 28
    strings_start = hdr + 4 * len(strings)
    pool = struct.pack("<HHIIIIII", 0x0001, hdr, strings_start + len(data), len(strings), 0,
                       0x100 if utf8 else 0, strings_start, 0)
    pool += struct.pack(f"<{len(strings)}I", *offsets) + data

    ids = [RES_IDS["minSdkVersion"], RES_IDS["targetSdkVersion"], RES_IDS["versionName"]]
    resmap = struct.pack("<HHI", 0x0180, 8, 8 + 4 * len(ids)) + struct.pack(f"<{len(ids)}I", *ids)

    def attr(ns, name, value):
        if isinstance(value, str):
            return struct.pack("<IIIHBBI", ns, idx[name], idx[value], 8, 0, 0x03, idx[value])
        return struct.pack("<IIIHBBI", ns, idx[name], 0xFFFFFFFF, 8, 0, 0x10, value)

    def element(tag, attrs):
        body = struct.pack("<IIHHHHHH", 0xFFFFFFFF, idx[tag], 20, 20, len(attrs), 0, 0, 0)
        body += b"".join(attrs)
        return struct.pack("<HHIII", 0x0102, 16, 16 + len(body), 1, 0xFFFFFFFF) + body

    ns = idx[ANDROID_NS]
    m_attrs = [attr(ns, "versionName", version), attr(0xFFFFFFFF, "package", package)]
    if split:
        m_attrs.append(attr(0xFFFFFFFF, "split", split))
    chunks = element("manifest", m_attrs)
    sdk_attrs = []
    if min_sdk is not None:
        sdk_attrs.append(attr(ns, "minSdkVersion", min_sdk))
    if target_sdk is not None:
        sdk_attrs.append(attr(ns, "targetSdkVersion", target_sdk))
    chunks += element("uses-sdk", sdk_attrs)

    body = pool + resmap + chunks
    return struct.pack("<HHI", 0x0003, 8, 8 + len(body)) + body


def make_apk(path, package="com.example.app", min_sdk=21, target_sdk=28, libs=(), **kw):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("AndroidManifest.xml", make_axml(package, min_sdk, target_sdk, **kw))
        z.writestr("classes.dex", b"dex")
        for abi in libs:
            z.writestr(f"lib/{abi}/libfoo.so", abi.encode())
    return path


def quiet(fn, *a, **kw):
    with redirect_stdout(io.StringIO()) as buf:
        rc = fn(*a, **kw)
    return rc, buf.getvalue()


class ManifestTests(unittest.TestCase):
    def test_utf8_and_utf16_pools(self):
        for utf8 in (True, False):
            m = t.parse_manifest(make_axml("com.a.b", 19, 28, "2.5", utf8=utf8))
            self.assertEqual(m["manifest"]["package"], "com.a.b")
            self.assertEqual(m["manifest"]["versionName"], "2.5")
            self.assertEqual(m["uses-sdk"]["minSdkVersion"], 19)
            self.assertEqual(m["uses-sdk"]["targetSdkVersion"], 28)

    def test_rejects_text_xml(self):
        with self.assertRaises(t.ManifestError):
            t.parse_manifest(b"<?xml version='1.0'?><manifest/>")


class InspectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_compatible(self):
        i = t.inspect_apk(make_apk(self.tmp / "a.apk", libs=["armeabi-v7a", "x86"]))
        self.assertTrue(i.ok, i.errors)
        self.assertEqual(i.package, "com.example.app")
        self.assertEqual(i.abis, ["armeabi-v7a", "x86"])

    def test_too_new_android(self):
        i = t.inspect_apk(make_apk(self.tmp / "a.apk", min_sdk=26))
        self.assertFalse(i.ok)
        self.assertIn("Android 8.0", i.errors[0])

    def test_missing_min_sdk_means_any(self):
        i = t.inspect_apk(make_apk(self.tmp / "a.apk", min_sdk=None))
        self.assertTrue(i.ok, i.errors)

    def test_bundles_rejected(self):
        p = self.tmp / "a.xapk"
        p.write_bytes(b"x")
        self.assertFalse(t.inspect_apk(p).ok)
        p = self.tmp / "b.apk"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("base.apk", b"x")
            z.writestr("split_config.arm64_v8a.apk", b"x")
        self.assertIn("split", t.inspect_apk(p).errors[0])

    def test_split_part_rejected(self):
        i = t.inspect_apk(make_apk(self.tmp / "a.apk", split="config.arm64_v8a"))
        self.assertFalse(i.ok)

    def test_x86_only_rejected(self):
        self.assertFalse(t.inspect_apk(make_apk(self.tmp / "a.apk", libs=["x86_64"])).ok)

    def test_corrupt(self):
        p = self.tmp / "a.apk"
        p.write_bytes(b"not a zip")
        self.assertFalse(t.inspect_apk(p).ok)


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "app"

    def test_layout_and_lib_renaming(self):
        apk = make_apk(self.tmp / "dl.apk", package="com.x.y",
                       libs=["armeabi", "armeabi-v7a", "arm64-v8a", "x86", "x86_64"])
        rc, _ = quiet(t.main, ["prepare", str(apk), "--out", str(self.out)])
        self.assertEqual(rc, 0)
        d = self.out / "hutroops.com.x.y"
        self.assertTrue((d / "com.x.y.apk").is_file())
        self.assertEqual(sorted(p.name for p in (d / "lib").iterdir()), ["arm", "arm64"])
        self.assertEqual((d / "lib/arm/libfoo.so").read_bytes(), b"armeabi-v7a")  # v7a preferred
        self.assertEqual((d / "lib/arm64/libfoo.so").read_bytes(), b"arm64-v8a")

    def test_no_libs_no_lib_folder(self):
        apk = make_apk(self.tmp / "dl.apk")
        quiet(t.main, ["prepare", str(apk), "--out", str(self.out)])
        self.assertFalse((self.out / "hutroops.com.example.app/lib").exists())

    def test_incompatible_skipped_and_existing_kept(self):
        bad = make_apk(self.tmp / "bad.apk", package="com.bad", min_sdk=30)
        good = make_apk(self.tmp / "good.apk")
        rc, out = quiet(t.main, ["prepare", str(bad), str(good), "--out", str(self.out)])
        self.assertEqual(rc, 1)
        self.assertFalse((self.out / "hutroops.com.bad").exists())
        self.assertTrue((self.out / "hutroops.com.example.app").exists())
        rc, out = quiet(t.main, ["prepare", str(good), "--out", str(self.out)])
        self.assertEqual(rc, 1)
        self.assertIn("--overwrite", out)
        rc, _ = quiet(t.main, ["prepare", str(good), "--out", str(self.out), "--overwrite"])
        self.assertEqual(rc, 0)

    def test_folder_argument(self):
        make_apk(self.tmp / "one.apk", package="com.one")
        make_apk(self.tmp / "two.apk", package="com.two")
        rc, _ = quiet(t.main, ["prepare", str(self.tmp), "--out", str(self.out)])
        self.assertEqual(rc, 0)
        self.assertEqual(len(list(self.out.iterdir())), 2)


class UsbTests(unittest.TestCase):
    def setUp(self):
        self.usb = Path(tempfile.mkdtemp())
        for name, value in (("detect_filesystem", lambda p: "vfat"), ("USB_MAX_BYTES", 10 ** 18)):
            self.addCleanup(setattr, t, name, getattr(t, name))
            setattr(t, name, value)

    def test_ready(self):
        (self.usb / "b832bc61472727635baffcf25dd28e9f239273e2").mkdir()
        rc, out = quiet(t.check_usb, self.usb)
        self.assertEqual(rc, 0, out)

    def test_done_and_reset(self):
        (self.usb / "b832bc61472727635baffcf25dd28e9f239273e2_done").mkdir()
        rc, out = quiet(t.check_usb, self.usb)
        self.assertEqual(rc, 1)
        self.assertIn("reset-usb", out)
        rc, _ = quiet(t.reset_usb, self.usb)
        self.assertEqual(rc, 0)
        self.assertTrue((self.usb / "b832bc61472727635baffcf25dd28e9f239273e2").is_dir())

    def test_nested_folder_and_wrong_fs(self):
        (self.usb / "Custom App" / "b832bc61472727635baffcf25dd28e9f239273e2").mkdir(parents=True)
        t.detect_filesystem = lambda p: "exfat"
        rc, out = quiet(t.check_usb, self.usb)
        self.assertEqual(rc, 1)
        self.assertIn("FAT32", out)
        self.assertIn("Custom App", out)

    def test_bad_app_layout_and_macos_clean(self):
        (self.usb / "b832bc61472727635baffcf25dd28e9f239273e2").mkdir()
        d = self.usb / "app" / "hutroops.com.x"
        (d / "lib" / "armeabi-v7a").mkdir(parents=True)
        (d / "x.apk").write_bytes(b"")
        (self.usb / "._x.apk").write_bytes(b"")
        rc, out = quiet(t.check_usb, self.usb)
        self.assertEqual(rc, 1)
        self.assertIn("com.x.apk", out)
        self.assertIn("armeabi-v7a", out)
        self.assertIn("macOS", out)
        quiet(t.clean_macos, self.usb)
        self.assertFalse((self.usb / "._x.apk").exists())


if __name__ == "__main__":
    unittest.main()
