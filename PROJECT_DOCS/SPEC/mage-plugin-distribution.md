## Mage Plugin Distribution

The mage plugin is also delivered as a release. `just mage-dist` builds, from the working tree as it
stands — it makes no git check — two files into `dist/`, which is gitignored:

- `adjagent-mage-v<V>.tgz`, the plugin: one top-level `adjagent/` directory holding what
  `install --harness=mage` writes. It holds the plugin only, with no `kbase` executable, so one
  tarball serves every platform;
- `adjagent-mage-v<V>.tgz.asc`, its detached armored signature, made with the signer's default `gpg`
  secret key.

`<V>` is what `python3 -m adjagent version` prints. The build refuses, before anything is removed or
written, a version not of the form `major.minor.patch`. Past that refusal, a re-run at the same
version replaces the two files, and a build that fails, signing included, leaves neither output of
that version and no `stage/` directory. The build signs with `gpg` and its default secret key, so the
operator runs it. It uploads, tags and pushes nothing: the operator publishes the two files by hand
to release `v<V>` of `benn-herrera/adjagent`.

The consumer downloads the tarball, may check it with `gpg --verify` against its `.asc`, and unpacks
it into `~/Mage/Skills/`; README.md gives the steps. No consumer installer is shipped, and nothing
checks the signature for the consumer.

The plugin's `.mcp.json` command is the bare `kbase`, resolved from `PATH` like every harness's
(Deployed Surfaces, above). Mage provides its servers access to system tools, so the name resolves
there.

