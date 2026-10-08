import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from devtools.render_diff import body, walk

OLD_BANNER = (
    b"---\n#\n# !GENERATED! from x\n# !TUNING! y\n# !BODY-SHA256! abc\n#\nname: a\n---\ntext\n"
)
NEW_BANNER = b"---\n# !GENERATED! from x\n# !TUNING! y\nname: a\n---\ntext\n"
BANNERED_BODY = b"---\n# !BANNER!\nname: a\n---\ntext\n"


def run_walk(a: Path, b: Path) -> list[str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        walk(a, b)
    return out.getvalue().splitlines()


class BodyTest(unittest.TestCase):
    def test_old_banner_replaced(self):
        self.assertEqual(body(OLD_BANNER), BANNERED_BODY)

    def test_new_banner_replaced(self):
        self.assertEqual(body(NEW_BANNER), BANNERED_BODY)

    def test_unbannered_files_unchanged(self):
        short_block = b"---\n#\n# !GENERATED! from x\nname: a\n"
        wrong_prefix = b"---\n#\n# !GENERATED! from x\n# !TUNING! y\n# other\n#\nname: a\n"
        for data in (b"no frontmatter\n# !GENERATED! from x\n", short_block, wrong_prefix):
            with self.subTest(data=data):
                self.assertEqual(body(data), data)


class WalkTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.a = Path(tmp.name) / "a"
        self.b = Path(tmp.name) / "b"
        self.a.mkdir()
        self.b.mkdir()

    def test_banner_only_difference_prints_nothing(self):
        (self.a / "f.md").write_bytes(OLD_BANNER)
        (self.b / "f.md").write_bytes(NEW_BANNER)
        self.assertEqual(run_walk(self.a, self.b), [])

    def test_body_difference_prints_one_line(self):
        (self.a / "f.md").write_bytes(NEW_BANNER)
        (self.b / "f.md").write_bytes(NEW_BANNER + b"more\n")
        self.assertEqual(run_walk(self.a, self.b), [f"Files {self.a / 'f.md'} and {self.b / 'f.md'} differ"])

    def test_one_sided_file_names_its_slot(self):
        (self.b / "only.md").write_bytes(b"x\n")
        self.assertEqual(run_walk(self.a, self.b), [f"Only in {self.b}: only.md"])


if __name__ == "__main__":
    unittest.main()
