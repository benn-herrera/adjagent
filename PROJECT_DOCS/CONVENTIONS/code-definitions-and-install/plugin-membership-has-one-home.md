### Plugin membership has one home

A plugin's members are decided in one place in code, its module in `adjagent/plugins/`, per definition
name: devpro by exclusion, kbase by enumeration. No harness, install step, render or test holds a
list of a plugin's members; each reads `Plugin.ships(name)`. A harness that renders nothing for a
definition declares it on `Harness.omits`. A change to a plugin module changes SPEC.md, Deployed
Surfaces, Plugins with it.
