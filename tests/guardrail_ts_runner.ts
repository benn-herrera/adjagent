// Runs opencode's guardrail plugin over a list of tool calls, for tests/test_guardrail.py.
//
// Usage: bun tests/guardrail_ts_runner.ts
// Stdin: a JSON array of {root, script, tool, input}: the project directory, the plugin copy staged
// for that run, and the call as opencode makes it. Stdout: a JSON array, in input order, of the
// message each call's hook threw, or null where it threw nothing.
//
// Run outside `bun test`: the "@opencode/plugin" stub must be registered before the plugin
// loads, and a static import would be hoisted above it.

Bun.plugin({
  setup(b) {
    b.module("@opencode/plugin", () => ({ loader: "object", exports: { Plugin: { define: (x: unknown) => x } } }))
  },
})

type Hook = (event: { tool: string; input: unknown }) => void
type GuardrailPlugin = {
  setup(ctx: { location: { directory: string }; tool: { hook(name: string, cb: Hook): Promise<void> } }): Promise<void>
}

const runs: { root: string; script: string; tool: string; input: unknown }[] = JSON.parse(await Bun.stdin.text())
const out: (string | null)[] = []
for (const { root, script, tool, input } of runs) {
  const plugin: GuardrailPlugin = (await import(script)).default
  let before: Hook | undefined
  await plugin.setup({
    location: { directory: root },
    tool: {
      async hook(name, cb) {
        if (name === "execute.before") before = cb
      },
    },
  })
  if (!before) throw new Error("the plugin registered no execute.before hook")
  try {
    before({ tool, input })
    out.push(null)
  } catch (e) {
    out.push((e as Error).message)
  }
}
console.log(JSON.stringify(out))
