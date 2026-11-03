### Kinds

`kind` decides where the definition goes, what frontmatter the harness emits for it, and which
fields it takes. `folder` is the path below the output root for a nested output, empty where the
definition's own output sits directly under its surface; a skill refuses it, because the directory
name is the definition's name on every harness.

| Kind | Output | Frontmatter | Fields |
|---|---|---|---|
| agent | `agents/<folder>/<name>.md` | the harness's agent fields, the model from `tier` through the tier map | `description`, `tools`, `tier` required; `color` optional |
| document | `agents/<folder>/<name>.md` | the harness's document fields: none under claude, `mode: subagent` and `disable: true` under opencode | none of the agent fields |
| command | `commands/<folder>/<name>.md` | no field lines, and no blank line after the closing fence | none of the agent fields |
| skill | `skills/<name>/SKILL.md`, then `skills/<name>/<file.path>` for each `SkillFile` | `name` and `description`, the two fields every harness reads, between the banner and the closing fence | `description` required; no `tools`, `tier` or `color`; `files` optional |
| agents file | none | none; renders to a block, see Agents File | none of the agent fields |

Every rendered definition's own output opens with a frontmatter block carrying the banner; a skill's
supporting files open with the comment form of it (see Banner). The skill row's two field lines are
the renderer's own (`render._field_lines`), not the harness's: they are deliberately
harness-invariant, because every harness reads the same two fields and none has anything of its
own to say about them. A `Definition` refuses at construction any field outside its kind's contract.

