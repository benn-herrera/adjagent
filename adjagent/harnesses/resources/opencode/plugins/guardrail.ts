// !INSTALLED! from adjagent/harnesses/resources/ — do not edit here: request changes from the adjagent project
//
// opencode v2.X plugin
// Prevents in-place edits using shell tools, redirects model to use EditTool and WriteTool
// On a kb install, also keeps every call out of kb-root/.index/, which kbase's own tools own.

import { Plugin } from "@opencode/plugin"
import { existsSync, realpathSync, statSync } from "node:fs"
import { basename, dirname, join, resolve, sep } from "node:path"
import { fileURLToPath } from "node:url"

const shellTools = new Set(["bash", "shell"])

// Scratch trees a command may write into without the edit tools.
const scratch = [".opencode-temp", "test-data/transient"]

// A kb install's signal, the kbase skill in this plugin's own harness directory: never the project
// directory, which --subdir makes wrong.
const kbSignal = fileURLToPath(new URL("../skills/kbase/SKILL.md", import.meta.url))

// kbase's records, in <root>/kb-root/.index/.
const kbRecords = ["nodes.yaml", "edges.yaml", "format.yaml"]
const indexPath =
  "kb-root/.index/ holds kbase's records: read them with kbase's `query` tool and change them with its `write` tool"
const indexSearch = `${indexPath}; exclude .index from this search (grep: --exclude-dir=.index; rg: -g '!**/.index/**'; find: -path '*/.index' -prune; Grep: a glob (opencode: include) no .index file matches; Glob: a pattern no .index file matches)`
const excludesIndex =
  /--exclude-dir[= ]['"]?\.index\b|(?:^|\s)(?:-g|--glob)[= ]['"]?!['"]?[^\s'"]*\.index|-(?:path|name)\s+['"]?[^\s'"]*\.index['"]?\s+-prune/
const patchPath = /^\*\*\* (?:Add File|Delete File|Update File|Move to): (.+)$/gm

type Input = { [arg: string]: string | undefined }

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

// real follows symlinks through the longest existing prefix of a lexically resolved path, so a path
// is judged where it lands; the part that does not exist stays as written.
function real(abs: string): string {
  let head = abs
  let tail = ""
  while (!existsSync(head) && head !== dirname(head)) {
    tail = join(basename(head), tail)
    head = dirname(head)
  }
  try {
    return join(realpathSync(head), tail)
  } catch {
    return abs
  }
}

function under(p: string, dir: string): boolean {
  return p === dir || p.startsWith(dir + sep)
}

// globRegExp reads one path segment as a glob over *, ?, […] and {a,b}.
function globRegExp(glob: string): RegExp {
  let re = ""
  let depth = 0
  for (const [t] of glob.matchAll(/\[[!^]?[^\]]+\]|[*?{},]|[^*?[{},]+|\[/g)) {
    const range = /^\[([!^]?)(.+)\]$/s.exec(t)
    if (t === "*") re += ".*"
    else if (t === "?") re += "."
    else if (t === "{") {
      re += "(?:"
      depth++
    } else if (t === "}" && depth) {
      re += ")"
      depth--
    } else if (t === "," && depth) re += "|"
    else if (range) re += `[${range[1] ? "^" : ""}${range[2]}]`
    else re += t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  }
  return new RegExp(`^(?:${re}${")".repeat(depth)})$`, "s")
}

// globRoot is a glob's leading literal segments, those before the first holding a glob character.
function globRoot(pattern: string): string {
  const segs = pattern.split("/")
  const n = segs.findIndex((s) => /[*?[{]/.test(s))
  return segs.slice(0, n < 0 ? segs.length : n).join("/")
}

// searchReason judges a search rooted at base whose file filter is a glob, or undefined for none:
// one rooted in kb-root/ is refused unless its filter cannot match a record.
function searchReason(base: string, filter: string | undefined, kb: string, subject: string): string | null {
  if (under(base, subject)) return indexPath
  if (!under(base, kb)) return null
  if (filter) {
    const re = globRegExp(filter.replace(/^.*\//s, ""))
    if (!kbRecords.some((name) => re.test(name))) return null
  }
  return indexSearch
}

// shellIndexReason refuses a command with a word resolving into the subject, and a recursive
// search or walk rooted in kb-root/ that does not exclude .index. Existence checks pass.
function shellIndexReason(cmd: string, cwd: string, kb: string, subject: string): string | null {
  for (const part of cmd.replace(heredocBody, "$1").split(/(?:&&|\|\||;|\||\n)/)) {
    const ws = part.trim().split(/\s+/).filter(Boolean)
    const name = (ws[0] ?? "").split("/").pop()
    if (name === "stat" || ((name === "test" || name === "[") && /^-[edf]$/.test(ws[1] ?? ""))) continue
    if (ws.some((w) => under(real(pathOf(w, cwd)), subject))) return indexPath
    const args = ws.slice(1)
    const recursive =
      name === "rg" ||
      name === "find" ||
      name === "tree" ||
      (name === "grep" && args.some((a) => /^-[a-zA-Z]*[rR]/.test(a) || /^--(?:dereference-)?recursive$/.test(a))) ||
      (name === "ls" && args.some((a) => /^-[a-zA-Z]*R/.test(a) || a === "--recursive"))
    if (!recursive || excludesIndex.test(part)) continue
    if ([".", ...args.filter((a) => !a.startsWith("-"))].some((a) => under(real(pathOf(a, cwd)), kb))) return indexSearch
  }
  return null
}

// indexReason names why a call reaches into <root>/kb-root/.index/, or null where it does not. A
// path collapses .. against cwd, then follows symlinks, as the root's own kb-root/ does.
function indexReason(tool: string, input: Input, cwd: string, root: string): string | null {
  const kb = real(resolve(root, "kb-root"))
  const subject = real(resolve(root, "kb-root/.index"))
  const at = (p: string | undefined) => real(pathOf(p ?? "", cwd))
  if (shellTools.has(tool)) return shellIndexReason(input.command ?? "", cwd, kb, subject)
  switch (tool) {
    case "read":
    case "write":
    case "edit":
      return under(at(input.path), subject) ? indexPath : null
    case "patch":
      return [...(input.patchText ?? "").matchAll(patchPath)].some((m) => under(at(m[1].trim()), subject))
        ? indexPath
        : null
    case "grep":
      return searchReason(at(input.path), input.include, kb, subject)
    case "glob":
      return searchReason(real(pathOf(globRoot(input.pattern ?? ""), pathOf(input.path ?? "", cwd))), input.pattern, kb, subject)
  }
  return null
}

export default Plugin.define({
  id: "guardrail-plugin",
  async setup(ctx) {
    const root = ctx.location.directory
    await ctx.tool.hook("execute.before", (event) => {
      const tool = String(event.tool ?? "").toLowerCase()
      const shell = shellTools.has(tool)
      const input = (event.input ?? {}) as Input
      const cwd = shell ? resolve(root, input.workdir ?? ".") : root
      const refusal = existsSync(kbSignal) ? indexReason(tool, input, cwd, root) : null
      if (refusal) throw new Error(`Blocked: ${refusal}`)
      if (!shell) return
      const reason = mutation(input.command ?? "", cwd, root)
      if (reason) {
        throw new Error(
          `Blocked: ${reason}. Use the edit and write tools for file changes; command output and other scratch belongs under .opencode-temp/.`,
        )
      }
    })
  },
})
