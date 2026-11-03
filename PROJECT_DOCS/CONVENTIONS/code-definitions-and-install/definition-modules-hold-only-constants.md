### Definition modules hold only constants

A definition module holds nothing but imports, string constants and `DEFINITIONS`. It reads
top to bottom as the file it renders. `just test` fails on any other top-level statement or call.
A skill's supporting files are `SkillFile(path=…, body=…)` values inside its `files=`, each body
held to the same rule as a definition body.
