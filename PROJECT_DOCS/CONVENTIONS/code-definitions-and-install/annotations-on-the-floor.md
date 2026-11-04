### Annotations on the floor

The Python floor is 3.9, and a union written `X | Y` does not evaluate there. A module that
annotates with a PEP 604 union opens with `from __future__ import annotations`, which keeps its
annotations unevaluated. A union evaluated at runtime, outside an annotation, is spelled
`typing.Union`; `Tools` in `adjagent/vocabulary.py` is the one such. Nothing reads annotations at
runtime, so lazy annotations change no behaviour.

`.venv` prefers `/usr/bin/python3` on macOS, the Xcode command-line tools' 3.9.6, so `just test`
there is the floor's check: a 3.10-only construct fails there. Elsewhere the venv runs on whatever
`python3` is installed, and `just test` does not check the floor. Using the repository directly does
not require Python 3.9.
