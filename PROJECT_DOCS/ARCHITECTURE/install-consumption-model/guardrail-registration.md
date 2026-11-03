### Guardrail registration

- **Probe.** Before `_refuse_foreign_targets`, the install runs the source script once, with
  `GUARDRAIL_INTERPRETER` and no `CLAUDE_PROJECT_DIR`, on one allowed Bash call, and requires exit
  0 within `GUARDRAIL_PROBE_SECONDS`. A missing interpreter, a missing module, a broken script and
  a hang all fail it. A failed probe never refuses the install. It drops the script from the files
  copied, skips the settings merge and its pre-write check, and reports one line naming the exit
  status and first stderr line, the timeout, or the `OSError`. A script and entry an earlier
  install wrote stay, and the line names them — the script when it carries the installed header,
  the settings file when it holds an element `claim` accepts — since the copy is one-way and prune
  never removes an `!INSTALLED!` file. The probe is one allowed call, not the case table, which
  runs in the test suite only.
- **Settings merge**, which `guardrail_merge` runs as `mcp_merge` runs the MCP entry's, both behind
  one pre-write read, `_check_settings`, and one path report, `_settings_obstacle`. The read
  refuses a non-UTF-8 file, and, in plain JSON, a key on the container path of the wrong type,
  `null` included: for the guardrail a `hooks` that is not an object or a `PreToolUse` that is not
  an array. `_settings_obstacle` names a symlink at the settings path or below the project on the
  way to it, dangling or not, which is never written through; a non-directory on that way; and
  anything but a regular file at the path. The read passes such a path and the merge reports it with
  the entry printed and leaves it, so neither merge raises after the first write. An absent file is
  written whole with the one entry. A present file is spliced as the MCP entry's is, every other
  byte kept, with an array scanner beside `_object` and an element insert beside `_with_member`; an
  absent `hooks` or `PreToolUse` is created as `_splice` creates a missing container.
  `install.py` holds the splice and the one, ambiguous or append decision, and no Claude settings
  layout or command shape: the container, the entry and the recogniser come from the
  `GuardrailHook`. Ours is a `PreToolUse` element `claim` accepts, a `hooks` array holding a command
  that equals, in full, what the entry builder writes for some harness directory; no substring
  counts, so a project's own hook running another `guardrail.pl` is not ours, and a command in an
  earlier shape is not either. Exactly one such element holding only our command is replaced whole;
  none is appended. More than one, or one holding our command beside others, is reported for a hand
  merge and the file left untouched, because replacing it whole would delete the project's own
  hook. Ours is recognised for any harness directory, so two installs under different `--subdir`
  values share one settings file and the later replaces the earlier's entry: a project has one
  guardrail.
  A JSONC file, or one the splice cannot place with certainty, is reported with the entry printed
  and left as it stands. Other `PreToolUse` entries are never touched.

The merge runs on every claude install whose probe passes, kb or not, and on
`install-agents-here`'s: the settings file is the project's own, so it passes through no banner
check and has no `REPO_ROOT` exemption, unlike the include line below, which is not written when
the project is this repository.

