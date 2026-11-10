// Runs opencode's plugin entry, index.ts, under a stub plugin context, for tests/test_opencode_entry.py.
//
// Usage: bun tests/opencode_entry_runner.ts
// Stdin: JSON {entry, directory, writes, command}: the installed entry; the project directory; files
// ({path, text}) written one at a time, each awaited until a reload its watcher triggers changes what is
// registered; and a command ({name, path, text, user}) executed with the user's text before and after
// its body file is replaced by text.
// Stdout: JSON {id, hooks, states, prompts}: the plugin id, the tool hooks it registered, what it had
// registered after setup and after each write, and the text each execute prompted.
// The runner fails where an execute's prompt drops the invocation's session id or delivery. It exits
// once the plugin's cleanup has run; a watcher the cleanup left open keeps it running.
//
// Run outside `bun test`: the "@opencode/plugin" stub must be registered before the entry loads.

import "./opencode_plugin_stub.ts"
import { writeFileSync } from "node:fs"

type Input = {
  entry: string
  directory: string
  writes: { path: string; text: string }[]
  command: { name: string; path: string; text: string; user: string }
}
type Command = { name: string; description?: string; execute(input: unknown): Promise<void> }

// A domain as opencode's State keeps one: every registered transform re-runs against a fresh
// value on each reload.
function domain<Value, Editor>(fresh: () => Value, editorOf: (value: Value) => Editor) {
  const callbacks: ((editor: Editor) => void)[] = []
  const d = {
    value: fresh(),
    build() {
      const value = fresh()
      for (const callback of callbacks) callback(editorOf(value))
      d.value = value
    },
    async transform(callback: (editor: Editor) => void) {
      callbacks.push(callback)
      d.build()
      return { dispose: async () => {} }
    },
    async reload() {
      d.build()
      onReload()
    },
  }
  return d
}

type Agent = { permissions: unknown[] } & Record<string, unknown>
const agent = domain(
  () => new Map<string, Agent>(),
  (agents) => ({
    update(id: string, update: (agent: Agent) => void) {
      const current = agents.get(id) ?? {
        mode: "primary",
        hidden: false,
        permissions: [{ action: "*", resource: "*", effect: "allow" }],
      }
      update(current)
      agents.set(id, current)
    },
  }),
)
const skill = domain(
  () => new Map<string, { id: string }>(),
  (skills) => ({ add: (s: { id: string }) => void skills.set(s.id, s) }),
)
const command = domain(
  () => new Map<string, Command>(),
  (commands) => ({ add: (c: Command) => void commands.set(c.name, c) }),
)
const mcp = domain(
  () => new Map<string, unknown>(),
  (servers) => ({ set: (name: string, config: unknown) => void servers.set(name, config) }),
)
let onReload = () => {}
// reloaded resolves at the first reload after which the registered state differs from the state at
// the call: a reload set off before a write can read the files before the write lands. A refresh
// rebuilds every domain synchronously, so by the time the promise settles all of them reflect it.
function reloaded(): Promise<void> {
  const before = JSON.stringify(state())
  return new Promise((done) => {
    onReload = () => {
      if (JSON.stringify(state()) !== before) done()
    }
  })
}

function state() {
  return {
    agents: Object.fromEntries(agent.value),
    skills: Object.fromEntries(skill.value),
    commands: Object.fromEntries([...command.value].map(([name, c]) => [name, c.description ?? null])),
    mcp: Object.fromEntries(mcp.value),
  }
}

const input: Input = JSON.parse(await Bun.stdin.text())
const prompts: string[] = []
const hooks: string[] = []
const invocation = { sessionID: "ses_1", delivery: "queue" }
const plugin = (await import(input.entry)).default
const cleanup = await plugin.setup({
  location: { directory: input.directory },
  tool: {
    async hook(name: string) {
      hooks.push(name)
    },
  },
  agent,
  skill,
  command,
  mcp,
  session: {
    async prompt(p: { text: string; sessionID: unknown; delivery: unknown }) {
      if (p.sessionID !== invocation.sessionID || p.delivery !== invocation.delivery) {
        throw new Error(`the prompt did not pass the invocation through: ${JSON.stringify(p)}`)
      }
      prompts.push(p.text)
    },
  },
})

const states = [state()]
for (const { path, text } of input.writes) {
  const done = reloaded()
  writeFileSync(path, text)
  await done
  states.push(state())
}

const execute = () => {
  const c = command.value.get(input.command.name)
  if (!c) throw new Error(`no command ${input.command.name} is registered`)
  return c.execute({ ...invocation, prompt: { text: input.command.user } })
}
await execute()
writeFileSync(input.command.path, input.command.text)
await execute()

await cleanup()
console.log(JSON.stringify({ id: plugin.id, hooks, states, prompts }))
