You are reading one document of a knowledge base a paragraph at a time, deciding of each paragraph
whether it states a result of its own.

Every answer is one letter:

- **@!letter-claim!@ — states a result**: the paragraph itself asserts a theorem, a relation it
  derives, a bound, a condition under which something holds, or a conclusion it draws from an
  argument. A result stated in plain prose counts, and one sentence asserting it is enough.
- **@!letter-not-a-claim!@ — states none**: motivation, signposting, a recap of a result stated
  elsewhere, notation, a definition, or narrative. A notation table or a section preamble states no
  result of its own.

## The document: `@!dyn.document!@`

Each labelled line is one sentence in the document's own words; the label and the colon after it
belong to this rendering, not to the document. A blank line ends a paragraph, and a paragraph is
named by the range of its labels. Unlabelled lines — navigation and frontmatter, headings, and any
block the document marks as a claim, a proof or a definition — are context only.

````````````markdown
@!dyn.body!@
````````````

## The question

The paragraph is @!dyn.paragraph!@:

````````````markdown
@!dyn.paragraph-text!@
````````````

Does this paragraph state a result of its own?
Answer @!letter-claim!@ if it does, @!letter-not-a-claim!@ if it does not: exactly one letter, and
nothing else.@!correction!@
