### Guardrail registration

- **Probe.** Before `_refuse_foreign_targets`, the install runs the source script once, with
  `GUARDRAIL_INTERPRETER` and no `CLAUDE_PROJECT_DIR`, on one allowed Bash call, and requires exit
  0 within `GUARDRAIL_PROBE_SECONDS`. A missing interpreter, a missing module, a broken script and
  a hang all fail it. A failed probe drops the script and the registration from the files written.
  Its report line carries the exit status and first stderr line, the timeout, or the `OSError`, and
  names an earlier install's script or registration by its installed banner or marker. The probe is
  one allowed call, not the case table, which runs in the test suite only.
- **Registration.** `GuardrailHook.registration` is written as a harness-rendered file. It is
  written only where the probe passed, so a registration never names a script that does not run. It
  is rendered from a constant command, so no settings merge, no project-root path and no
  harness-directory quoting is involved, and `--subdir` does not change it.

- **Opencode.** It declares no `GuardrailHook`, so it has no probe and no registration file. Its
  registration is the plugin entry, which runs `guardrail.ts` within itself (Guardrail
  hook).

A user-level install runs no probe: `install` takes no guardrail for it.

