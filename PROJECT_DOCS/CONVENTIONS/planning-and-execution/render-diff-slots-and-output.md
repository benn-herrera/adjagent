### `render-diff` slots and output

`just render-diff [a] [b]` takes its two slots positionally and reports pairs, not spans. Both
slots are positional parameters with defaults: `just render-diff` compares `reference-claude` against
`latest`, and `just render-diff my-slot` compares `my-slot` against `latest`. A slot is a bare
word — `a=reference-claude` is read as the first slot's own name, so the run fails on a slot that does
not exist. A slot holds a slot project per plugin (`rendered/<slot>/devpro/`, `rendered/<slot>/kbase/`),
so a pair is a file at the same path below both slots, slot project included. A file on one side only (`Only in`) has no second file for `diff -u`: read it under the
slot that holds it. A pair's changed spans come
from `diff -u` on its own two files under `rendered/<slot>/`. The list is a footprint, not the
change: a `reference-*` slot holds what was accepted at the last `just retake-reference`, so a pair carries
every change accepted since as well, and the pair of names says nothing about which of them one
run made.
