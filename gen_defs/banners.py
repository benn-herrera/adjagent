"""
The banner is a five-line YAML-comment block naming the source template
(`# !GENERATED! from templates/agents/<name>.md.tmpl ...`) above a `!TUNING!`
line and the body hash:

    #
    # !GENERATED! from <tmpl> and <chunks> — edit those. DO NOT HAND EDIT ...
    # !TUNING! family=<file> seat=<tier|none> member=<member|none>
              tier=<tier map> pin=<pin map> stock=<tiers|none> harness=<name>
    # !BODY-SHA256! <hex>
    #

(one physical line for `!TUNING!`; wrapped here only to fit). `family=` and
the two maps are the render's whole triple, both maps EFFECTIVE — post-merge —
and serialized in TIERS order rather than sorted, so the claim is deterministic
and reads highest-to-lowest. `seat=` and `member=` are this definition's OWN
resolution: the tier its pin site declared and the family member its overlays
resolved against, `none` for an output with no pin site. They are carried
because the pin map is not injective (`low` and `lowest` both default to
haiku), so a definition's tier cannot be recovered by inverting it — recording
the answer is what keeps a definition's tuning readable from the definition
alone. `member=` is redundant with tier[seat] in a well-formed banner, and that
is the point: it is the cheap cross-check catching a banner written under one
tier map and read under another. `stock=` lists the tiers whose mapped member
declares zero [family.*.models.<member>] tables in the loaded family, or `none`.
`harness=` names the harness file the render's @!hrn.<key>!@ markers resolved
from. It is the last field and optional to a reader: a banner written before
it existed parses with no harness claimed.
The banner always lives inside YAML frontmatter, never in the body that becomes
a prompt:

  - An agent template must open with a frontmatter block; the banner is
    injected at its top.
  - A command template whose body opens with a frontmatter block gets the
    banner injected the same way; a command template with no frontmatter gets
    a minimal frontmatter block emitted above its body, containing only the
    banner comment lines, so the banner never lands in the literal prompt
    text.

Its `# !BODY-SHA256! <hex>` line is the sha256 of everything the file
holds AFTER the banner block, exactly as written — the one line both banner
kinds share. It lets any later reader answer a question the banner alone
cannot: is this file still the bytes the tool wrote, or has someone edited it
since? A file whose body hashes to its own claim is provably untouched tool
output — reproducible at will, and therefore safe to overwrite without a
backup (see the safety table, `generation` module docstring). A pre-1.5.0
banner carries no hash line and proves nothing, so it is treated as possibly
hand-edited.

A definition without a banner is presumed hand-maintained and outside this
tool's remit; if it should be generated, delete it and re-run.
"""

import hashlib
import re
from pathlib import Path
from typing import NamedTuple

from .model_tuning import Tuning, map_spec
from .paths import SHARED_CHUNKS, rel

# The banner, read back out of a definition as its claim to being generated.
# Deliberately path-agnostic: any *.md.tmpl claim marks the file as generated,
# which is the whole question write safety and the install's prune ask of it.
# Whether the claimed template still exists is nobody's question here — a
# definition no template declares is retired by the prune, not by a verdict.
BANNER_CLAIM = re.compile(r"^# !GENERATED! from (\S+\.md\.tmpl)\b", re.MULTILINE)
# The banner's hash line and the line that closes the block around it: the
# hash of everything after it, and the marker for where "everything after it"
# begins. Matching both together means one search locates the claim and the
# bytes it covers — for either banner kind, since an !INSTALLED! banner in an
# HTML comment closes with "-->" where the others close with "#".
BODY_HASH_CLAIM = re.compile(r"^# !BODY-SHA256! ([0-9a-f]{64})\n(?:#|-->)\n", re.MULTILINE)
# The banner's tuning claim: the whole triple this definition was rendered
# under, plus its own seat and member, and the harness — optional on read. A MACHINE claim — read back and compared
# field for field, so it is bracket-free, one token per field, and must stay
# stable across versions or a definition rendered by an older build stops
# reading. The run-report echo (report_tuning) is the display form and is
# deliberately a separate serialization.
TUNING_CLAIM = re.compile(
    r"^# !TUNING! family=(\S+) seat=(\S+) member=(\S+) tier=(\S+) pin=(\S+) stock=(\S+)(?: harness=(\S+))?$",
    re.MULTILINE,
)


def sha256_text(text: str) -> str:
    """Content hash as the banner records it, over utf-8 bytes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tuning_line(tuning: Tuning, *, seat: str | None) -> str:
    """The banner's !TUNING! line: the run's whole triple, plus this
    definition's own seat and the member it resolved against, then the
    harness.

    `seat`/`member` are deliberately not spelled `tier` — that key is already
    spent on the tier MAP, and two different things named tier in one line is
    how a parser and a human come to disagree. An output with no pin site
    records `seat=none member=none`.
    """
    member = "none" if seat is None else tuning.tier_map[seat]
    return (
        f"# !TUNING! family={rel(tuning.family)}"
        f" seat={seat or 'none'} member={member}"
        f" tier={map_spec(tuning.tier_map)} pin={map_spec(tuning.pin_map)}"
        f" stock={','.join(tuning.stock) or 'none'}"
        f" harness={tuning.harness}"
    )


def banner(template: Path, *, body_hash: str, tuning: Tuning, seat: str | None = None) -> str:
    """The five-line YAML-comment block stamped into frontmatter.

    `body_hash` is the sha256 of everything that will follow the block — the
    definition's claim to being unmodified since it was written. The !TUNING!
    line sits ABOVE it, because BODY_HASH_CLAIM matches the hash line together
    with the `#` closing the block around it. `tuning` is always present: with
    --family defaulting to claude there is no untuned render left to represent.
    """
    return (
        "#\n"
        f"# !GENERATED! from {rel(template)} and {rel(SHARED_CHUNKS)}"
        " — edit those. DO NOT HAND EDIT THIS FILE.\n"
        f"{tuning_line(tuning, seat=seat)}\n"
        f"# !BODY-SHA256! {body_hash}\n"
        "#"
    )


def banner_body(text: str) -> str | None:
    """Everything after the banner block — the bytes its !BODY-SHA256! line
    covers — or None when the file carries no hash-stamped banner."""
    match = BODY_HASH_CLAIM.search(text)
    return None if match is None else text[match.end() :]


def body_untouched(text: str) -> bool:
    """Is this file provably unmodified tool output, its post-banner bytes
    hashing to exactly what its own banner claims? A pre-1.5.0 banner carries
    no hash line, proves nothing, and is treated as possibly hand-edited.

    Line endings are translated first, and that is what makes this the single
    write-safety reading ARCHITECTURE.md promises rather than two. Generation
    reads its targets through read_text, whose universal newlines hand this
    function a CRLF target already translated; install reads raw bytes and hands
    it the CRLF through. Without the translation here the same file is
    unmodified output to one caller and hand-written content to the other, and a
    consumer tree some tool normalized to CRLF backs every file up, on every
    re-install, under a line accusing the operator of edits nobody made.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    match = BODY_HASH_CLAIM.search(text)
    return match is not None and match.group(1) == sha256_text(text[match.end() :])


def frontmatter_of(text: str) -> str | None:
    """Return the YAML frontmatter block, or None if the file has none."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:i])
    return None


def banner_claim(text: str) -> str | None:
    """Return the template path a definition's banner claims, if it has one."""
    front = frontmatter_of(text)
    if front is None:
        return None
    match = BANNER_CLAIM.search(front)
    return match.group(1) if match else None


class TuningClaim(NamedTuple):
    """A banner's !TUNING! line, parsed back. Strings throughout: it is a claim
    read off a file, compared against another claim, never re-resolved.
    `harness` is None for a banner written before the field existed."""

    family: str
    seat: str
    member: str
    tier: str
    pin: str
    stock: str
    harness: str | None = None


def tuning_claim(text: str) -> TuningClaim | None:
    """Return the tuning a definition's banner claims, or None when it carries
    no !TUNING! line (a bannerless file, or one written before 3.0.0)."""
    front = frontmatter_of(text)
    if front is None:
        return None
    match = TUNING_CLAIM.search(front)
    return TuningClaim(*match.groups()) if match else None


# The !INSTALLED! banner: what a copied file says about itself. Deterministic
# text — nothing dated, nothing per-run — so an unchanged source re-installs to
# the identical bytes.
INSTALLED_NOTICE = "!INSTALLED! from the adjagent repo — do not edit in place; " "edit the source repo and re-install."


def stamp_installed(text: str, *, style: str) -> str:
    """`text` with an !INSTALLED! banner stamped in, in `style`'s comment
    syntax, above the bytes its !BODY-SHA256! line covers.

    Four styles, one block: "frontmatter" opens the file's own YAML block and
    injects at its top (a frontmatter reader drops the comment lines, so the
    banner never reaches the prompt); "bare-frontmatter" emits a minimal block
    holding only the banner above a file that has none, exactly as
    render_template does for a frontmatter-less command template; "html" wraps
    the block in an HTML comment above content that must not gain frontmatter;
    "hash" puts it at the top of the file, below a shebang when there is one.
    The hashed body is everything after the block in every case, so
    banner_body / body_untouched read either banner kind without knowing which
    it met.
    """
    prefix = ""
    if style in ("frontmatter", "bare-frontmatter"):
        prefix = "---\n"
        body = text[len("---\n") :] if style == "frontmatter" else "---\n" + text
        opening, closing = "#\n", "#\n"
    elif style == "html":
        body = text
        opening, closing = "<!--\n", "-->\n"
    else:
        body = text
        if text.startswith("#!"):
            shebang, _, body = text.partition("\n")
            prefix = shebang + "\n"
        opening, closing = "#\n", "#\n"
    return f"{prefix}{opening}# {INSTALLED_NOTICE}\n" f"# !BODY-SHA256! {sha256_text(body)}\n{closing}{body}"
