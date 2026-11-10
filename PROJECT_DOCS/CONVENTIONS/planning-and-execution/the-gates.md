### The gates

```
edit gate: `just test-changed [base]`
checkpoint gate: `just test`, then `just sweep-python` (A checkpoint includes the sweep)
step-down application: the dispatch's `model` parameter
```

The edit gate runs only the test surfaces the change touches (the mapping lives in the justfile's
`TEST_SURFACE_MAP`; a change to `PROJECT_DOCS/`, `docs/` or a top-level `*.md` selects the `docs`
surface, the link and tree check). Cross-surface coupling is removed, not paid for by running
unrelated surfaces.
