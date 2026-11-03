### The gate after a change

The gate after a change is `just test-changed [base]`. It runs only the test surfaces the
change touches (the mapping lives in the justfile's `TEST_SURFACE_MAP`; a change to `PROJECT_DOCS/` or a
top-level `*.md` selects the `docs` surface, the link and tree check); bare `just test` is the
full run. Cross-surface coupling is removed, not paid for by running unrelated surfaces.
