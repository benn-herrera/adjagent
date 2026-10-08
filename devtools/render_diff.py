"""Compare two rendered slots under `rendered/` by body.

A file whose first line is `---` and whose next lines match exactly one of the two banner shapes
(`OLD`, `NEW`) has those lines replaced by the constant line `# !BANNER!`; any other file is
compared whole. Replacing rather than deleting means a file that loses its banner still differs,
and a block of any other shape stays in place, so it shows as a difference rather than hiding one.

The module reads only the two slots and never imports the generator.

Output and exit contract: prints `diff -rq`'s two line forms, `Only in <dir>: <name>` and
`Files <a> and <b> differ`. Exits 0 whether or not differences exist; exits 1 only when a slot does
not exist.
"""

import filecmp
import sys
from pathlib import Path

RENDERED_DIR = Path(__file__).resolve().parent.parent / "rendered"

# Line 2 onward of a bannered file, per shape: a lone `#` must match exactly,
# every other entry is a prefix. The pre-1.0 shape's line 2 is a lone `#`,
# so the two shapes cannot both match one file.
OLD = (b"#", b"# !GENERATED! from ", b"# !TUNING! ", b"# !BODY-SHA256! ", b"#")
NEW = (b"# !GENERATED! from ", b"# !TUNING! ")


def body(data: bytes) -> bytes:
    lines = data.split(b"\n")
    for shape in (OLD, NEW):
        head = lines[1:1 + len(shape)]
        if lines[0] == b"---" and len(head) == len(shape) and all(
                line == want if want == b"#" else line.startswith(want) for line, want in zip(head, shape)):
            return b"\n".join([b"---", b"# !BANNER!", *lines[1 + len(shape):]])
    return data


def walk(a: Path, b: Path) -> None:
    cmp = filecmp.dircmp(a, b, ignore=[])
    for name in sorted(set(cmp.left_list) | set(cmp.right_list)):
        if name in cmp.left_only:
            print(f"Only in {a}: {name}")
        elif name in cmp.right_only:
            print(f"Only in {b}: {name}")
        elif name in cmp.common_dirs:
            walk(a / name, b / name)
        elif name not in cmp.common_files or body((a / name).read_bytes()) != body((b / name).read_bytes()):
            print(f"Files {a / name} and {b / name} differ")


def main(argv: list[str] | None = None) -> int:
    slugs = sys.argv[1:] if argv is None else argv
    if len(slugs) != 2:
        print("usage: python -m devtools.render_diff <slot-a> <slot-b>", file=sys.stderr)
        return 2
    slots = [RENDERED_DIR / slug for slug in slugs]
    for slug, slot in zip(slugs, slots):
        if not slot.is_dir():
            print(f"error: {slot} does not exist — run 'just render {slug}' first", file=sys.stderr)
            return 1
    walk(*slots)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
