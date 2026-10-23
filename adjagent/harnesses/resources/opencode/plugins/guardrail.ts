// !INSTALLED! from adjagent/harnesses/resources/ — do not edit here: request changes from the adjagent project
//
// opencode v2.X plugin
// Prevents in-place edits using shell tools, redirects model to use EditTool and WriteTool

import { Plugin } from "@opencode/plugin"
import { statSync } from "node:fs"
import { basename, join, resolve, sep } from "node:path"

const shellTools = new Set(["bash", "shell"])

// Scratch trees a command may write into without the edit tools.
const scratch = [".opencode-temp", "test-data/transient"]

function pathOf(word: string, cwd: string): string {
  return resolve(cwd, word.replace(/^["']|["']$/g, ""))
}

function inScratch(abs: string, root: string): boolean {
  return scratch.some((dir) => {
    const base = resolve(root, dir)
    return abs === base || abs.startsWith(base + sep)
  })
}

function stat(abs: string) {
  try {
    return statSync(abs)
  } catch {
    return undefined
  }
}

// free is whether a target is a device, a descriptor duplication (2>&1), or scratch.
function free(word: string, cwd: string, root: string): boolean {
  if (!word || word.startsWith("&") || word === "-") return true
  const abs = pathOf(word, cwd)
  return abs.startsWith("/dev/") || inScratch(abs, root)
}

// redirects reads each >, >>, >|, >! and >&file target, skipping heredoc bodies,
// which are not shell. A quoted span is matched whole, so a > inside it is never
// examined, and the [^>=-] before an operator skips -> and =>. A >& before a
// digit or - duplicates or closes a descriptor and writes nothing.
const heredocBody = /((?<!<)<<-?\s*(["']?)(\w+)\2[^\n]*)[\s\S]*?(?:\n[ \t]*\3(?=\n|$)|$)/g
const redirect = /"([^"]*)"|'([^']*)'|(?:^|[^>=-])>(?:>|&(?![\d-]))?[|!]?\s*(?:"([^"]*)"|'([^']*)'|([^\s;&|<>]+))/g

function redirects(cmd: string): string[] {
  const out: string[] = []
  for (const m of cmd.replace(heredocBody, "$1").matchAll(redirect)) {
    const target = m[3] ?? m[4] ?? m[5]
    if (target) out.push(target)
  }
  return out
}

const inPlace = /\b(?:g?sed|perl|ruby)\b[^\n;&|]*\s(?:-[a-zA-Z0-9]*ie?\b|--in-place\b)/
const script = /\b(?:python[0-9.]*|ruby|perl|node)\b[^\n]*(?:\s-(?:c|e)\b|<<-?\s*['"]?\w+)/
const writes = /(?:open\s*\([^)]*['"][wa]b?\+?['"]|(?:writeFile|appendFile)(?:Sync)?\s*\(|createWriteStream\s*\(|(?<!stdout)(?<!stderr)\.write\s*\(|\.write_(?:text|bytes)\s*\()/

// mutation names the first form that would change a file behind the edit
// tools' back, or null where the command is free of them. Relative targets
// resolve against cwd, scratch trees against root.
function mutation(cmd: string, cwd: string, root: string): string | null {
  if (inPlace.test(cmd.replace(/"[^"]*"|'[^']*'/g, " "))) {
    return "an in-place sed, perl or ruby edit"
  }
  for (const target of redirects(cmd)) {
    if (!free(target, cwd, root)) return `a redirect that writes ${target}`
  }
  for (const part of cmd.split(/(?:&&|\|\||;|\||\n)/)) {
    const ws = part.trim().split(/\s+/).filter(Boolean)
    const name = (ws[0] ?? "").split("/").pop()
    if (name === "tee") {
      for (const word of ws.slice(1)) {
        if (!word.startsWith("-") && !free(word, cwd, root)) return `tee writing ${word}`
      }
    }
    if (name === "cp" || name === "mv") {
      const args = ws.slice(1).filter((w) => !w.startsWith("-"))
      const dest = args.pop()
      if (!dest) continue
      const abs = pathOf(dest, cwd)
      const hit = stat(abs)?.isDirectory() ? args.map((src) => join(abs, basename(pathOf(src, cwd)))) : [abs]
      if (!inScratch(abs, root) && hit.some((p) => stat(p)?.isFile())) return `${name} overwriting ${dest}`
    }
  }
  if (script.test(cmd) && writes.test(cmd)) return "an inline script that writes a file"
  return null
}

export default Plugin.define({
  id: "guardrail-plugin",
  async setup(ctx) {
    const root = ctx.location.directory
    await ctx.tool.hook("execute.before", (event) => {
      if (!shellTools.has(String(event.tool ?? "").toLowerCase())) return
      const input = event.input as { command?: string; workdir?: string } | undefined
      const reason = mutation(input?.command ?? "", resolve(root, input?.workdir ?? "."), root)
      if (reason) {
        throw new Error(
          `Blocked: ${reason}. Use the edit and write tools for file changes; command output and other scratch belongs under .opencode-temp/.`,
        )
      }
    })
  },
})
