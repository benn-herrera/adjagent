### `render-diff` slots and output

`just render-diff [a] [b]` takes its two slots positionally and reports pairs, not spans. Both
slots are positional parameters with defaults: `just render-diff` compares `reference` against
`latest`, and `just render-diff my-slot` compares `my-slot` against `latest`. A slot is a bare
word — `a=reference` is read as the first slot's own name, so the run fails on a slot that does
not exist. A file present on one side only is reported `Only in <dir>: <name>`, so there is no
second file to hand `diff -u`: read it under the slot that holds it. A pair's changed spans come
from `diff -u` on its own two files under `rendered/<slot>/`. The list is a footprint, not the
change: `reference` holds what was accepted at the last `just retake-reference`, so a pair carries
every change accepted since as well, and the pair of names says nothing about which of them one
run made.
