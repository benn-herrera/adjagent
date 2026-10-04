# README - kb_tools testing

Integration testing harness and fixtures for kb- commands, agents, and kb_tools.

## Pointing a build at your own endpoint

Every model call a build makes is one request to the server its environment names, in
`liaison_tools`' env format: `API_BASE_URL` (the API root, `/v1` included), `MODEL`, `API_KEY_FILE`
(the file holding the key) and, for plaintext http to a host that is not loopback, `ALLOW_HTTP=1`.
No config key names a server or a model, and a `[claude]` section is refused at load like any other
section nothing reads. A run with a model call left to walk refuses an environment that names no
server before its first stage, naming the missing variable; a `--no-inference` run needs none. Keep
the env file outside the repository: it is yours, not the project's.

## Building a hand-staged fixture with inference

`just kb-driver-fixture <dir> <env-file> [--resume] [--sources=<a.tex>,<b.tex>,...] [stage-fixture flags] [-- kb_driver run flags]`
(`dir` and `env-file`, like `stage-fixture`'s `dir`, are absolute or relative to the directory you
ran `just` from, so `just -f kb-testing/justfile ...` from the repository root takes
`kb-testing/test-data/transient/ModernCorp`; `env-file` is `~` expanded) restages the fixture
(`stage-fixture`, which refuses while a run holds the repository's lock), then launches a
with-inference build over it detached and returns. A leading `--resume` skips staging and relaunches
over the fixture as it stands, so the driver continues from its ledger; it refuses a fixture with no
installed toolchain or no `kb-build:` ledger commit. The env file is sourced into the driver's
environment only and is never printed. It names the server every model call of the build goes to, in
the `liaison_tools` variables above. Sources are the fixture's top-level `.tex` files that hold
`\documentclass`, unless a leading `--sources=<a.tex>,<b.tex>,...` (either order with `--resume`)
names exactly the files to build, relative to `dir` and in that order; it refuses an empty list, a
duplicate, and a file that is missing or holds no `\documentclass`. With `--resume` the named subset
goes to the driver as given; the ledger is the driver's concern. For example,
`just kb-driver-fixture test-data/transient/ModernCorp ~/.config/reaper-qwen3.8-flash-next.env --sources=ModernCorp.tex,ModernCorpShort.tex --family=qwen3`.
The pid file, console log and run directory land in
`.claude-temp/kb-driver-live/`, so `just kb-driver-harvest` and `just kb-driver-kill` apply; one
such run at a time. Flags before `--` go to staging (`--family=qwen3`), flags after it to the driver
(`--through <stage>`).

## Papers this corpus does not contain

The arXiv survey corpus is declared per category in `justfile` (`ARXIV_*`). Some papers have been
drawn and then removed, and the reasons are worth keeping so they are not drawn again.

**Source pandoc cannot parse.** The build reads LaTeX through pandoc and does nothing to the source
first. Where pandoc's own parser fails — verified by running `pandoc -f latex -t json <source>` from
the paper's directory with no filters and none of this project's flags — the paper measures nothing
about this pipeline, so it leaves the corpus rather than being worked around. **Massaging raw LaTeX
into shape before the reader sees it is out of scope**: it is a second LaTeX implementation living
in this repository, and the pipeline's whole premise is that pandoc is the one thing that knows how
LaTeX is read.

Removed on that ground: `2609.10029v1` (econ.TH), `2609.10235v1` (physics.optics), `2609.10392v1`
(eess.AS), `2609.10474v1` (math.PR). Why each one defeats pandoc is not recorded and is not worth
establishing — the test is the exit code, and a paper that fails it is out.

Some of these are pandoc reaching into a **style or class file** rather than the paper's own text,
which is a property of the venue's template and not of what the author wrote — so a replacement
drawn from the same venue can fail the same way. Validate a candidate with bare pandoc before
adopting it.

**Source pandoc parses cleanly while dropping what it includes.** Worse than a hard failure, because
nothing downstream can see it: pandoc exits **0**, warns only on stderr, and produces a document
with the included files' content simply absent — so every partition check compares one copy of the
gap against another and passes. `2609.09821v1` (cs.GR) is removed on that ground. The test is a
`Could not load include file` warning on stderr, which is invisible in the exit code; a candidate
that emits one is out.

**Submissions with no LaTeX at all.** arXiv serves a PDF from `/e-print` for a submission that
shipped no source, with a 200 and nothing distinguishing it before it is unpacked. Two
physics.optics draws were such. That category holds two ids for both reasons together.
