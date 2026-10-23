"""One module per harness, each defining `HARNESS`, a `Harness`; the module name
is the `--harness` value. The type is `adjagent.harness`; a harness module holds
no class. The `resources/` tree beside them is no module: it holds the files a
harness ships into its project harness directory, one directory per harness,
copied as they stand (`adjagent.install`)."""
