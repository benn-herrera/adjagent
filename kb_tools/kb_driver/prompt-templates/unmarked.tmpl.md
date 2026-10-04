You are reading claims of a mathematical text, deciding whether one claim's own text points at
another claim's result where no cross-reference links the two. The other claim may be stated in the
same document or in a different one.

Every answer is one letter:

- **@!letter-points!@ — points at it**: the source claim's own words take up the candidate's
  result. They describe it, restate it, apply it, assume it as a condition, or use notation the
  candidate introduces for what it states.
- **@!letter-does-not-point!@ — does not**: the source claim's own words take up no part of the
  candidate's result. Sharing a subject or standard notation is not pointing, and neither is a
  pointer made only by another paragraph of the document that the claim's words do not take up.

## The document: `@!dyn.document!@`

The source claim is stated in this document, and shown again below. The document is here so that
the claim's words can be resolved: where the claim says "this escape" or "the bound above", the
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

Does the source claim's own text point at the candidate's result?
Answer @!letter-points!@ if it does, @!letter-does-not-point!@ if it does not: exactly one letter,
and nothing else.@!correction!@
