### Opencode entry

`adjagent/harnesses/resources/opencode/index.ts` is opencode's plugin entry (SPEC.md, Deployed
Surfaces, Shipped files). It is written for opencode v2.2.6 and is the same file for both plugins. The
install copies it, with `guardrail.ts`, to the install directory as a harness resource (Renders and
copies); a user-level install copies the entry alone.

**The opencode API it uses.** It imports `Plugin` from `@opencode/plugin` and exports
`Plugin.define({ id, setup })`.

- `id` is the registry's `plugin`, read synchronously from `registry.json` because opencode takes the id
  before `setup` runs; an unreadable registry falls back to the install directory's name.
- `setup(ctx)` receives four domains, `ctx.agent`, `ctx.skill`, `ctx.command` and `ctx.mcp`. Each has
  `transform(callback)`, which hands the callback an editor: `update(id, fn)` for agents, `add` for
  skills and commands, `set(name, config)` for MCP servers. Each also has `reload()`, which makes
  opencode run its transforms again. `ctx.session.prompt` delivers a command's text.
- `setup` returns an async cleanup, which opencode calls when the plugin module goes.

The entry declares the slice of the context it reads as local types. Nothing checks them against
opencode itself: the tests run the entry under a stub of this surface
(`tests/opencode_plugin_stub.ts`, `tests/opencode_entry_runner.ts`).

**What it does.**

- *Guardrail first.* Where `guardrail.ts` stands beside it, `setup` awaits that module's `setup`
  before registering anything or starting the watcher, so a failed guardrail leaves no watcher
  running. A user-level install has no `guardrail.ts`, and none runs.
- *Registry read.* It parses `registry.json` as the shape the opencode harness renders and validates
  nothing; the renderer is the only writer (Rendering, Harnesses and families). It reads each agent
  and skill body with async `readFile` and strips the leading comment lines, and the blank line
  after them, that carry the banner. A body or registry it cannot read is logged and left out; the
  rest registers.
- *Registration.* Each agent record updates the agent of that id: the body as its system text, the
  description, mode, hidden flag, model and color where the record has them, and each permission as
  an allow or deny rule on every resource. Each skill is added with its id as its name, its path
  and its body. Each MCP record is set under its name.
- *Commands.* A command's body is read when the command runs, banner stripped, and prepended to the
  text the operator typed; a read failure names the file. The session id and delivery mode pass
  through to `ctx.session.prompt` unchanged.
- *Watcher.* A recursive `fs.watch` on the install directory schedules a refresh after a 100 ms
  quiet period. Refreshes are serialized on one promise chain, so an older read never replaces a
  newer one. A refresh re-reads the registry and calls the four `reload()`s; a failure is logged and the
  next change tries again. The watcher has an error listener that logs. The cleanup clears the
  pending refresh, closes the watcher and awaits a refresh in flight.
