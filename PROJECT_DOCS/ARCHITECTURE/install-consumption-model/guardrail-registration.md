### Guardrail registration

- **Probe.** Before `_refuse_foreign_targets`, the install runs the source script once, with
  `GUARDRAIL_INTERPRETER` and no `CLAUDE_PROJECT_DIR`, on one allowed Bash call, and requires exit
  0 within `GUARDRAIL_PROBE_SECONDS`. A missing interpreter, a missing module, a broken script and
  a hang all fail it. A failed probe never refuses the install. It drops the script and the
  registration from the files written, skips the retired-entry removal and the flat script's
  removal, and reports one line naming the exit status and first stderr line, the timeout, or the
  `OSError`. What an earlier install left stays, and the line names it: the script under ROOT, and
  under the harness directory where the flat layout put one, when it carries the installed header;
  the registration when it carries its marker; and a project settings file holding an item a
  retired entry's `claim` accepts. The probe is one allowed call, not the case table, which runs in
  the test suite only.
- **Registration.** `GuardrailHook.registration` is written as a harness-file-class target: a file
  at its path without the marker refuses the install like any foreign harness file, and one with it
  is replaced whole. It is written only where the probe passed, so a registration never names a
  script that does not run. It is a render of a constant command, so no settings merge, no
  project-root path and no harness-directory quoting is involved, and `--subdir` does not change it.
- **Retired entries.** `Harness.retired_entries` lists what earlier installs registered in files
  the project owns. Each `RetiredEntry` names the settings file, the container path, the member key
  (empty where the entry is an array element), a `claim` recogniser, the `Replacement` whose
  write licenses the removal, and a `trace`. Claude has two. The guardrail's `PreToolUse` element in
  `.claude/settings.json`, recognised by `_guardrail_claim`, is removed on a project install whose
  probe passed. The `kbase` member of the project `.mcp.json`'s `mcpServers`, recognised by
  `_kbase_claim` from its command alone (the bare `kbase`, or a path ending in it), is removed on a
  project install that writes the kb MCP entry. A user-level install removes none: it never wrote
  either.
- **Removal**, which `_remove_retired_entry` runs behind `_settings_obstacle` and
  `_editable_settings`, and which never refuses the install. `_settings_obstacle` names a
  symlink at the path or below the project on the way to it, dangling or not, which is never written
  through; a non-directory on that way; and anything but a regular file at the path.
  `_editable_settings` yields the text only of UTF-8 plain JSON whose container path holds the types
  it needs; an unreadable or non-UTF-8 file, one that is not a JSON object, and one with a
  wrong-typed key on the path (`null` included) yield nothing. Each is left untouched, so removal
  never raises after the first write. An absent file, or one holding
  no item a `claim` accepts, is left with nothing said. Exactly one item the `claim` reads as ours
  alone is cut out by `_without_item`, which removes the item and the separator joining it to a
  neighbour, keeps every other byte, and closes an emptied container to `[]` or `{}` in place.
  `install.py` holds the removal and the one-or-ambiguous decision, and no Claude settings layout:
  the container, the member and the recogniser come from the `RetiredEntry`. A guardrail command is
  ours only when equal, in full, to what an earlier install wrote for some harness directory; no
  substring counts, so a project's own hook running another `guardrail.pl` is not ours. More than
  one such item, or one holding our command beside others, is reported with each printed for a hand
  removal and the file left untouched, because removing it whole would delete the project's own
  hook. A file `_editable_settings` yields nothing for (comments included), one the scanner cannot
  delimit with certainty, and a path `_settings_obstacle` names are left untouched, and reported as
  a stranded entry only where the text found there, read as UTF-8 through a symlink and with
  undecodable bytes replaced (`_names_text`), contains the `trace`: the missing-script report for the
  guardrail, `"kbase"` for the MCP entry. A file holding neither is not mentioned. Other
  `PreToolUse` entries and other `mcpServers` members are never touched.
- **Flat script.** On a project install under a harness directory that is not ROOT, whose probe
  passed, `_remove_retired_script` removes `<harness-dir>/hooks/guardrail.pl` when it is a regular
  file, reached through no symlink, with the `!INSTALLED! … adjagent` header, then `hooks/` if that
  leaves it empty. The same install has written the plugin's script, its replacement.

A user-level install runs neither the probe nor the removal: `install` takes no guardrail for it.

The removal runs on every claude project install that writes its replacement, and on
`install-agents-here`'s: the settings files are the project's own, so they pass through no banner
check and have no `REPO_ROOT` exemption, unlike the kb include line, which is not written when the
project is this repository (Base and kb installs).
