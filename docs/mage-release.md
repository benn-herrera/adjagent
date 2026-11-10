# Mage plugin release

The mage plugin is published as a release: one tarball and detached signature per plugin. Unpack
one; `<plugin>` below is `devpro` or `kbase` ([Plugins](installing.md#plugins)). The tarballs hold the
plugin only; the kbase plugin's `kbase` MCP command is the bare `kbase`, so you install kbase yourself
([Knowledge base](knowledge-base.md#requirements)). Contract:
[SPEC](../PROJECT_DOCS/SPEC/mage-release.md).

1. Download `adjagent-mage-<plugin>-v<version>.tgz` from the release `v<version>` of
   [benn-herrera/adjagent](https://github.com/benn-herrera/adjagent/releases), and optionally its
   `adjagent-mage-<plugin>-v<version>.tgz.asc`.
2. Optionally check the tarball against the signature. Fetch the release signer's public key over WKD
   (the developer's key is at <https://keyoxide.org/wkd/benn@bennherrera.dev>), then verify:

   ```sh
   gpg --auto-key-locate wkd --locate-external-keys benn@bennherrera.dev
   gpg --verify adjagent-mage-<plugin>-v<version>.tgz.asc adjagent-mage-<plugin>-v<version>.tgz
   ```

3. Unpack it into Mage's skills directory, removing any earlier copy first:

   ```sh
   rm -rf ~/Mage/Skills/<plugin>
   tar -xzf adjagent-mage-<plugin>-v<version>.tgz -C ~/Mage/Skills/
   ```

   The tarball has one top-level `<plugin>/` directory, so this leaves `~/Mage/Skills/<plugin>`.
4. For the kbase plugin, install kbase if you have not. Native Windows is unsupported for it.
5. For the kbase plugin, restart Mage so it starts the `kbase` MCP server; the plugin's entry
   finds `kbase` on `PATH`. Do the same after installing or upgrading kbase while Mage is running.
