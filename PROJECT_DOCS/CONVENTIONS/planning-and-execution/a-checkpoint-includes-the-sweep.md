### A checkpoint includes the sweep

A checkpoint is not complete until the sweep has run. `just sweep-python` enumerates what no
single file can report — one concept with two implementations, one constant with two definitions
— because a rule honoured completely inside one file is still broken across two. It emits
candidates and never verdicts, so the run is not finished when it exits zero; it is finished when
someone has read the list and said which pairs are one idea.
