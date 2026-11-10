### Where it goes

One module in `adjagent/definitions/`; its existence is its enrollment, and
nothing imports it by name. Definitions that ship together share one group module.

A new definition joins devpro by existing. To also ship it in kbase, add it to SPEC.md, Deployed
Surfaces, Plugins and to `adjagent/plugins/kbase.py`.
