## Mage Release

Each mage plugin is also delivered as the mage release: one tarball and one signature
(Deployed Surfaces, Plugins), four files in all, published at release `v<V>` of `benn-herrera/devpro`
(`https://github.com/benn-herrera/devpro`), where `<V>` is what `python3 -m devpro --version`
prints. For each plugin `<plugin>`:

- `devpro-mage-<plugin>-v<V>.tgz`, the plugin: one top-level `<plugin>/` directory holding what
  `install --plugin=<plugin> --harness=mage` writes and nothing else, with no AppleDouble (`._*`) entries or
  extended-attribute headers. It holds the plugin only, with no `kbase` executable, so one
  tarball serves every platform;
- `devpro-mage-<plugin>-v<V>.tgz.asc`, its detached armored signature.

The operator downloads one tarball, may check it with `gpg --verify` against its `.asc`, and
unpacks it into `~/Mage/Skills/`. Unpacking leaves in place any file an earlier copy holds that
this release does not, so the operator removes `~/Mage/Skills/<plugin>` first. `docs/mage-release.md` gives the
commands. No installer for the operator is shipped, and nothing checks the signature for the
operator.

Only the kbase tarball holds the `kbase` MCP entry and `kb-tools/`. The entry's command is the bare
`kbase`, resolved from `PATH` like every harness's (SPEC.md, Deployed Surfaces, Plugins). Mage
provides its servers access to system tools, so the name resolves there.

