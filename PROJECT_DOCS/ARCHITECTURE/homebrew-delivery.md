## Homebrew Delivery

The mechanism behind the distribution channel of SPEC.md, Package and Command and the Homebrew
install of SPEC.md, Guide and README. Two repositories are in it, and each owns what the other
cannot: this one owns the version and the tag, and the tap — `benn-herrera/tap`, holding
`Formula/devpro.rb` — owns the formula, its `url` and its `sha256`. The archive the formula points
at is GitHub's tag archive, not a build product of this repository.

The tap is a sibling clone, `homebrew-tap/`, gitignored and never part of the package.
`just tap-repo` runs `devtools/scripts/tap-repo.sh`, which is a copy of the tap's own script
because the clone cannot set itself up: it clones
`git@github.com:benn-herrera/homebrew-tap.git` where the directory is absent, adds that origin to a
repository that has none, and refuses a directory that is no repository or whose origin is another,
so a second run changes nothing. The URL is the script's own, and the clone's location is the
justfile's `HOSTED_TAP_DIR`, passed to it as `TAP_DIR`.

`just tap-update` runs the tap's `scripts/justfile` with `TAP_FORMULA=devpro`, and the tap's
`tap-update.sh` does the rest: it reads the formula's `depends_on` line for its language, takes that
language's version report — devpro's `python3 -m devpro --version`, read in this checkout — and so
names the release archive
`https://github.com/benn-herrera/devpro/archive/refs/tags/v<version>.tar.gz`: GitHub's archive of
the pushed tag `just tag` cut. It downloads that archive and takes its sha256, rewrites the
formula's `url` and `sha256` through the tap's `tap-formula-set.sh`, pulls the tap, and commits the
formula alone, signed and pushed by nothing. An unpushed tag fails there, naming the tag and the
repository.

`just tap-local` rehearses the same delivery against the working tree instead of a release:
`tap-local.sh` tars every file `git ls-files` names at its working-tree content into `dist/tap/`,
prefixes the archive with `v<version>/`, copies the tap's formula to a scratch formula in that
directory whose `url` is that tarball and whose `sha256` is its own, and reinstalls `devpro` from it
through a local tap of its own. The tap clone and Homebrew's own tap checkout are written by nothing
in it, and the machine's Homebrew `devpro` is replaced.
