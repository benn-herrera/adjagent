### Runner include line is exact

The runner include line is a byte-level edit of a file the project does not own. The
consumer's justfile or Makefile is read and written with `newline=""`, so a rewrite keeps each
line's own ending instead of translating it to the host's. Only a live line matches: one whose
first non-blank character is `#` is a comment about an install, never an include. The rewrite
splices the installed snippets-path token in place of the path the line already names and keeps
the rest of the line, so an assignment's left-hand side and a trailing comment survive. A file
holding more than one matching line is reported for the operator to merge by hand, never
half-rewritten.
