import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from devtools.render_diff import body, text, walk

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


class TextTest(unittest.TestCase):
    def test_a_paragraph_wrapped_two_ways_compares_equal(self):
        self.assertEqual(text(b"one two\nthree  four\n"), text(b"one\ntwo three four\n"))

    def test_a_paragraph_split_into_two_differs(self):
        self.assertNotEqual(text(b"one two\nthree four\n"), text(b"one two\n\nthree four\n"))

    def test_a_fence_with_different_indentation_differs(self):
        self.assertNotEqual(text(b"```\nif x:\n    y\n```\n"), text(b"```\nif x:\n  y\n```\n"))

    def test_inline_code_with_triple_backticks_is_not_a_fence(self):
        self.assertEqual(
            text(b"```def f(x: int)```\n-> int:\n"),
            text(b"```def f(x: int)```  -> int:\n"),
        )
        self.assertEqual(
            text(b"intro ```def f(x: int) -> int:```\nmore\n"),
            text(b"intro\n```def f(x: int) -> int:``` more\n"),
        )

    def test_a_fence_with_an_info_string_stays_exact(self):
        self.assertNotEqual(
            text(b"```python\nif x:\n    y\n```\n"), text(b"```python\nif x:\n  y\n```\n"))

    def test_a_tilde_fence_is_not_closed_by_backticks(self):
        self.assertNotEqual(
            text(b"~~~\n```\nif x:\n    y\n~~~\n"), text(b"~~~\n```\nif x:\n  y\n~~~\n"))

    def test_list_items_wrapped_differently_compare_equal(self):
        self.assertEqual(
            text(b"- one two\n  three\n- four  five\n"), text(b"- one\n  two three\n- four five\n"))

    def test_list_items_merged_into_one_differ(self):
        self.assertNotEqual(text(b"- one two\n- three\n"), text(b"- one two three\n"))

    def test_numbered_list_items_are_separate_units(self):
        self.assertEqual(text(b"1. one\n   two\n2) three\n"), text(b"1. one two\n2) three\n"))
        self.assertNotEqual(text(b"1. one two\n2. three\n"), text(b"1. one two 2. three\n"))

    def test_a_heading_is_its_own_exact_unit(self):
        self.assertNotEqual(text(b"## Heading\nbody text\n"), text(b"## Heading body text\n"))
        self.assertNotEqual(text(b"## Heading\n"), text(b"##  Heading\n"))
        self.assertEqual(text(b"#hashtag\nbody\n"), text(b"#hashtag body\n"))

    def test_table_rows_are_their_own_exact_units(self):
        self.assertNotEqual(text(b"| a | b |\n| c | d |\n"), text(b"| a | b | | c | d |\n"))
        self.assertNotEqual(text(b"intro\n| a |\n"), text(b"intro | a |\n"))
        self.assertNotEqual(text(b"| a |  b |\n"), text(b"| a | b |\n"))

    def test_frontmatter_with_a_changed_space_differs(self):
        self.assertNotEqual(text(b"---\nname: a\n---\ntext\n"), text(b"---\nname:  a\n---\ntext\n"))


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
