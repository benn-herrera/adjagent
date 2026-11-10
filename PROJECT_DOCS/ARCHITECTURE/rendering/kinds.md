### Kinds

`kind` decides where the definition goes, what frontmatter the harness emits for it, and which
fields it takes. `folder` is the path below the output root for a nested output, empty where the
rendered definition sits directly under its deployed surface; a skill refuses it, because the
directory name is the definition's name on every harness.

| Kind | Output | Frontmatter | Fields |
|---|---|---|---|
| agent | `agents/<folder>/<name>.md` | the harness's agent fields, the model from `tier` through the tier map; under opencode none, the same values in the registry record | `description`, `tools`, `tier` required; `color` optional |
| document | `agents/<folder>/<name>.md` | the harness's document fields: none under claude; under opencode none, a `hidden` `mode: subagent` registry record | none of the agent fields |
| command | `commands/<folder>/<name>.md` | no field lines, and no blank line after the closing fence; under opencode none, a registry record of id, body file and description | none of the agent fields |
| skill | `skills/<name>/SKILL.md`, then `skills/<name>/<file.path>` for each `SkillFile` | `name` and `description`, the two fields claude and mage read, between the banner and the closing fence; under opencode none, a registry record of id, description and `SKILL.md` path | `description` required; no `tools`, `tier` or `color`; `files` optional, each `SkillFile` path being kebab directory parts and a `.md` name |
| agents file | none | none; renders to a block, see Agents File | none of the agent fields |

Under claude and mage every rendered definition other than a supporting file opens with frontmatter
carrying the generated banner; a skill's supporting files, and every rendered file under opencode,
open with the comment form of it (see Banner). The skill row's two field lines are the renderer's
own (`render._field_lines`), not the harness's: they are deliberately identical under claude and
mage, because both read the same two fields and neither has anything of its own to say about them. A `Definition` refuses at construction any field outside its
kind's contract.

