import io, os, sys, tempfile, unittest, zipfile
from contextlib import redirect_stdout
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import x50_setup_usb as s  # noqa: E402

SCRIPT = "b832bc61472727635baffcf25dd28e9f239273e2"


def zbytes(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


class SetupUsbTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.urls = {
            s.UNINSTALL_V1: zbytes({f"uninstall v1/{SCRIPT}/run.sh": "a"}),
            s.UNINSTALL_V2: zbytes({f"{SCRIPT}/run.sh": "b", f"__MACOSX/{SCRIPT}/._x": "m"}),
        }
        self._orig_get = s._get
        s._get = lambda url: self.urls[url]
        self.calls = []
        self._orig_main = s.getapps.main
        s.getapps.main = lambda argv: self.calls.append(argv) or 0
        Path("custom.zip").write_bytes(zbytes({
            f"Custom App/install/{SCRIPT}/i.sh": "i", "Custom App/install/app/readme.txt": "r",
            f"Custom App/uninstall/{SCRIPT}/u.sh": "u"}))

    def tearDown(self):
        s._get, s.getapps.main = self._orig_get, self._orig_main
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_builds_all_steps(self):
        with redirect_stdout(io.StringIO()) as out:
            rc = s.main(["--out", "o", "--custom-app-zip", "custom.zip"])
        self.assertEqual(rc, 0, out.getvalue())
        o = Path("o")
        self.assertTrue((o / s.STEP1 / SCRIPT / "run.sh").exists())
        self.assertTrue((o / s.STEP2 / SCRIPT / "run.sh").exists())
        self.assertTrue((o / s.STEP3 / SCRIPT / "u.sh").exists())
        self.assertTrue((o / s.STEP4 / SCRIPT / "i.sh").exists())
        self.assertEqual(self.calls[0][:2], ["--out", str(o / s.STEP4 / "app")])
        self.assertIn("smarttube", self.calls[0])
        self.assertTrue((o / "HOW_TO_USE.txt").read_text(encoding="utf-8").startswith("HOW TO"))
        self.assertFalse(any(p.name.endswith("_tmp") for p in o.iterdir()))

    def test_zip_without_script_is_reported(self):
        self.urls[s.UNINSTALL_V1] = zbytes({"readme.txt": "x"})
        with redirect_stdout(io.StringIO()) as out:
            rc = s.main(["--out", "o", "--custom-app-zip", "custom.zip"])
        self.assertEqual(rc, 1)
        self.assertIn("no 'b832bc...' script folder", out.getvalue())


if __name__ == "__main__":
    unittest.main()
