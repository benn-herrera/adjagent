You are reading claims of a mathematical text, deciding whether one claim leans on another where no
cross-reference links the two. A claim leans on another when its own words use something that is set
out in the other claim: a result it applies or assumes, a condition or quantity it names by
description ("the bound above", "this estimate", "the condition of the previous section"), or
notation the other claim introduces. The other claim may be stated in the same document or in a
different one.

Every answer is one letter:

- **@!letter-points!@ — leans on it**: the candidate is where something the source claim uses is set
  out — introduced, stated in full, or shown — and the source claim takes it from there rather than
  setting it out itself.
- **@!letter-does-not-point!@ — does not**: the candidate is not where anything the source claim
  uses is set out. This is the answer when the two share only a subject or notation; when each sets
  out its own result on common ground; when both recount a result that is set out somewhere else,
  which the candidate may itself credit to another part, section, paper or claim; and when the
  pointer is made by a neighbouring paragraph of the document rather than by the source claim's own
  words.

## The document: `@!dyn.document!@`

The source claim is stated in this document, and shown again below. The document is here so that
the claim's words can be resolved: where the claim says "this estimate" or "the bound above", the
document says which one.

````````````markdown
@!dyn.body!@
````````````

## The source claim

@!dyn.claim-line!@

````````````markdown
@!dyn.claim-text!@
````````````

## The question

The candidate claim:

@!dyn.candidate-line!@

````````````markdown
@!dyn.candidate-text!@
````````````

Is the candidate where something the source claim uses is set out?
Answer @!letter-points!@ if it is, @!letter-does-not-point!@ if it is not: exactly one letter,
and nothing else.@!correction!@
