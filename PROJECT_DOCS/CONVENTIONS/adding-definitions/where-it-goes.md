### Where it goes

One module in `devpro/definitions/`; its existence is its enrollment, and
nothing imports it by name. Definitions that ship together share one group module.

A new definition joins the devpro plugin by existing. To also ship it in the kbase plugin, add it to
SPEC.md, Deployed Surfaces, Plugins and to `devpro/plugins/kbase.py`.
