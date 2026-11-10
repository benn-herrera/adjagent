## Bodies usable without frontmatter

The body of every rendered definition under `agents/`, the content after its banner carrier, is
usable without frontmatter as an external (non-Claude) model's system prompt. The banner carrier is
what the file opens with: the frontmatter block under claude and mage, the banner comment lines and
the blank line after them under opencode. Dropping it, every line through the one that closes the
frontmatter or the blank line that ends the comments, yields the body entire, losing no content and
needing no knowledge of what the frontmatter or the registry holds. No rendered definition ships
truncated. The install does not check it.
The extracted body does not carry the definition's model line, which
stays in the frontmatter, or under opencode in the registry, where the rendered definition carries
one: a caller that uses the body without a harness that reads either supplies the model itself.

