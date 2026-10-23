// Runs opencode's guardrail plugin over a list of commands, for tests/test_guardrail.py.
//
// Usage: bun tests/guardrail_ts_runner.ts <path to guardrail.ts>
// Stdin: a JSON array of {root, cwd, command}. Stdout: a JSON array, in input order, of the
// message each command's hook threw, or null where it threw nothing. A cwd other than the root
// reaches the hook as the shell tool's `workdir`; at the root none is sent, as opencode sends
// none when the call sets no working directory.
//
// Run outside `bun test`: the "@opencode/plugin" stub must be registered before the plugin
// loads, and a static import would be hoisted above it.

Bun.plugin({
  setup(b) {
    b.module("@opencode/plugin", () => ({ loader: "object", exports: { Plugin: { define: (x: unknown) => x } } }))
  },
})

type Hook = (event: { tool: string; input: { command: string; workdir?: string } }) => void
type GuardrailPlugin = {
  setup(ctx: { location: { directory: string }; tool: { hook(name: string, cb: Hook): Promise<void> } }): Promise<void>
}

const plugin: GuardrailPlugin = (await import(process.argv[2])).default
const cases: { root: string; cwd: string; command: string }[] = JSON.parse(await Bun.stdin.text())
const out: (string | null)[] = []
for (const { root, cwd, command } of cases) {
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
    before({ tool: "bash", input: cwd === root ? { command } : { command, workdir: cwd } })
    out.push(null)
  } catch (e) {
    out.push((e as Error).message)
  }
}
console.log(JSON.stringify(out))
