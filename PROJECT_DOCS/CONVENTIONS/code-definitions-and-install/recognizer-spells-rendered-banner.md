### Recognizer spells rendered banner

The install's recognizer spells the banner the renderer writes. `install.py` builds its
generated-file prefixes from `render.GENERATED_MARK`, so what recognises a generated file reads
the spelling the renderer writes. A test that plants a literal `!GENERATED!` banner does not hold
that binding — a change on either side passes it — so the case plants rendered output. A
harness-rendered file carries no banner: its `HarnessFile.marker` is what reads it as ours, and the
test plants a real render rather than a literal marker, for the same reason.
