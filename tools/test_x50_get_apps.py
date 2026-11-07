import hashlib, io, json, os, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import x50_get_apps as g  # noqa: E402
from test_x50_apk_prep import make_apk  # noqa: E402


class GetAppsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.files = {}
        new = Path("new.apk"); make_apk(new, package="org.schabi.newpipe", min_sdk=26)
        old = Path("old.apk"); make_apk(old, package="org.schabi.newpipe", min_sdk=21,
                                        libs=["armeabi-v7a"])
        vlc = Path("vlc.apk"); make_apk(vlc, package="org.videolan.vlc", min_sdk=17)
        self.files["https://dl/NewPipe_v2.apk"] = new.read_bytes()
        self.files["https://dl/NewPipe_v1.apk"] = old.read_bytes()
        rels = [
            {"tag_name": "v3-beta", "prerelease": True, "assets": []},
            {"tag_name": "v2", "assets": [{"name": "NewPipe_v2.apk", "browser_download_url": "https://dl/NewPipe_v2.apk"}]},
            {"tag_name": "v1", "assets": [{"name": "NewPipe_v1.apk", "browser_download_url": "https://dl/NewPipe_v1.apk"}]},
        ]
        self.files["https://api.github.com/repos/TeamNewPipe/NewPipe/releases?per_page=30"] = json.dumps(rels).encode()
        base = "https://get.videolan.org/vlc-android/last/"
        name = "VLC-Android-3.6.5-armeabi-v7a.apk"
        self.files[base] = f'<a href="{name}">x</a><a href="{name}.sha256">y</a>'.encode()
        self.files[base + name] = vlc.read_bytes()
        self.files[base + name + ".sha256"] = (hashlib.sha256(vlc.read_bytes()).hexdigest() + "  " + name).encode()
        g._get = lambda url: self.files[url]

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def run_main(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = g.main(list(args))
        return rc, buf.getvalue()

    def test_falls_back_to_older_release_and_lays_out(self):
        rc, out = self.run_main("--out", "app", "newpipe", "vlc")
        self.assertEqual(rc, 0, out)
        self.assertTrue(Path("app/hutroops.org.schabi.newpipe/org.schabi.newpipe.apk").exists())
        self.assertTrue(Path("app/hutroops.org.schabi.newpipe/lib/arm/libfoo.so").exists())
        self.assertTrue(Path("app/hutroops.org.videolan.vlc/org.videolan.vlc.apk").exists())
        self.assertIn("SHA-256 verified", out)

    def test_bad_checksum_fails(self):
        base = "https://get.videolan.org/vlc-android/last/VLC-Android-3.6.5-armeabi-v7a.apk"
        self.files[base + ".sha256"] = b"00" * 32
        rc, out = self.run_main("--out", "app", "vlc")
        self.assertEqual(rc, 1)
        self.assertIn("SHA-256 mismatch", out)

    def test_fdroid_newest_compatible(self):
        new = Path("r2.apk"); make_apk(new, package="net.programmierecke.radiodroid2", min_sdk=24)
        old = Path("r1.apk"); make_apk(old, package="net.programmierecke.radiodroid2", min_sdk=16)
        pkg = "net.programmierecke.radiodroid2"
        self.files[f"https://f-droid.org/api/v1/packages/{pkg}"] = json.dumps(
            {"packages": [{"versionName": "0.86", "versionCode": 86}, {"versionName": "0.90", "versionCode": 90}]}).encode()
        self.files[f"https://f-droid.org/repo/{pkg}_90.apk"] = new.read_bytes()
        self.files[f"https://f-droid.org/repo/{pkg}_86.apk"] = old.read_bytes()
        rc, out = self.run_main("--out", "app", "radiodroid")
        self.assertEqual(rc, 0, out)
        self.assertIn("0.86", out)
        self.assertTrue(Path(f"app/hutroops.{pkg}/{pkg}.apk").exists())

    def test_any_apk_prefers_release(self):
        self.assertEqual(g.pick_any_apk(["app-debug.apk", "app-release.apk", "notes.txt"]), "app-release.apk")

    def test_smarttube_asset_choice(self):
        names = ["SmartTube_beta_31.0_armeabi-v7a.apk", "SmartTube_stable_30.56_arm64-v8a.apk",
                 "SmartTube_stable_30.56_armeabi-v7a.apk", "SmartTube_stable_30.56_x86.apk"]
        self.assertEqual(g.pick_smarttube_asset(names), "SmartTube_stable_30.56_armeabi-v7a.apk")


if __name__ == "__main__":
    unittest.main()
