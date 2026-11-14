### Annotations on the floor

The Python floor is 3.9, and a union written `X | Y` does not evaluate there. A module that
annotates with a PEP 604 union opens with `from __future__ import annotations`, which keeps its
annotations unevaluated. A union evaluated at runtime, outside an annotation, is spelled
`typing.Union`; `Tools` and `RenderValue` in `devpro/vocabulary.py` are the two such. Nothing reads annotations at
runtime, so lazy annotations change no behaviour.

On macOS `just test` checks the floor (`justfile`'s `_venv`); elsewhere the venv runs on whatever
`python3` is installed, and nothing checks the floor. Running from a checkout needs Python 3.9 or
later, not 3.9 itself.
