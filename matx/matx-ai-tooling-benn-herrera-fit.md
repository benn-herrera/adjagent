# MatX AI Tooling / Benn Herrera Fit

[Benn Herrera](https://bennherrera.me)'s self-assessment of experience applicability to the problem space and requirements for the role of [Software Engineer, AI Tooling](https://jobs.ashbyhq.com/matx/4d6a4a63-2430-4ada-86b7-4c17cecad6b5).

Authorship note: This document was hand-authored. AI was used for review, but the content is mine. -bph

## Core Requirements

### Have RTL design, DV, or PD fluency, or will build it fast

#### Overlap
Will build it fast.

- I knew nearly nothing about Linux kernel drivers on the morning of Mon 21-Sept-2026
  - By end of day, with AI assistance, I had set up an AI tutoring dev & test workflow and started hand-coding my first driver in C (see linux-kernel-driver-sandbox in repo list)
  - By end of the Weds session (which bled into Thursday am) I had hand-written a full stack from a complete kernel driver to userspace lib and C++ driver test plus bound the userspace lib to a scripting language with an additional test in script
  - The device in question was QEMU's [EDU device](https://www.qemu.org/docs/master/specs/edu.html), created for supporting the Linux kernel lectures at Masaryk University. I powered through the device's full feature set in three days from a cold start.
  - Over the next two days, I designed, and with AI coding assistance, built a code gen system for keeping the userspace lib C API, a C++ RAII wrapper, and Lua script bindings in sync from a single source of truth. That part was just fun.
- Six months ago I knew absolutely nothing about the internals of inference beyond "it has to do with matrices". That was addressed with go-inference-lab-bench (see repo list)

Upshot: learning about new things by doing them (all out) is a standard MO with an established pattern

#### Delta
- No direct exposure to RTL, DV, or PD.

#### Questions
- Right now, too many and probably all the wrong ones. A couple days in will be another story.

### Use coding agents heavily and have strong opinions on what you let them do, what you don't, and how you verify their work

#### Overlap
Extensive, recent. 

- Heavy use and development of agent-coding workflows, including constraints and verification
  - One core aspect of what splits agent high/low competence is tasks that require multi-level balancing while writing
    - Coding agents consider questions in terms of what is immediately visible but frequently fail to consider the level above them. This results in over-engineering where they don't know it is not necessary and under-engineering where they don't know it is.
    - This pattern repeats for architecture & design agents and results in inflexible choices made due to unconsidered assumptions about the larger context or risky choices for the same reason
    - Contrast: when not writing, but examining an existing artifact, AI is outstanding with multi-tier considerations. This is why a develop/review cycle using agents driven by a human can keep projects on course
  - adjagent project - agent set generator with installable agents for multiple workflows
    - Multi-agent debate workflows included for design and review work - MAD review extremely useful for correcting project drift between feature sprints
    - Agent set defines process where all model-facing artifacts are reviewed by a prompt engineering focused agent
      - Catches issues with verbosity, consistency, logical contradictions
      - Catches and drafts revisions for language that is descriptive, but ineffective
    - install process offers safe-merging global rules to user's home CLAUDE.md
      - Includes restrictions to prevent silent accumulation of automatic behavior mods (they are unexamined, unreviewed, and non-portable)
  - See also "Notice LLM agents asserting something confidently wrong" section below
  - See "Repos" section below, every project makes use of agentic systems
- Agent harness used exclusively within sandbox. An unprivileged agent user runs all harness processes (see agent-sandboxing/ in adjagent repo)
- Built knowledge base agent system that distilled massive multi-volume math-heavy LaTeX corpus into navigable markdown with automated rigor tracking and maintenance tooling
  - Since creation it has been extracted, extended, generalized in kb_tools (see adjagent in repo list at end of doc)
  - Efficient context management
    - Multiple partial corpus reads regularly overflowed context window before questions could be posed
    - After conversion synthesizing multiple topics across disparate volumes became trivially easy
  - Rigor tracking - author pursues their ideas, rigor audit trail follows automatically
    - Utility split into inference vs deterministic roles. Inference for judgment and perception, deterministic tools used by agent for kb metadata maintenance
    - A docent agent handles exploration of kb with facilities for collecting, collating, caching topic session information
    - A maintainer agent handles changes to the kb, including updating rigor status across the claim graph via tooling
- Prototype agent harness, personant (see repo list at end of doc)
  - Designed for multi-year career of memory across multiple projects
  - One centralized memory and behavior locus, no scattered adjustment or recall files

#### Delta
- Heavy use in a personal rather than professional context

#### Questions
- To what extent are agents used for high-correctness and security sensitive operations (e.g. driver coding)?

### Built engineering workflows (methodology, flow automation, review tooling, agent harnesses) that other engineers adopted and kept

#### Overlap
Extensive, spanning career.

- Multiple instances of establishing processes adopted by others and kept, see [bennherrera.me](https://bennherrera.me/#examples) for long form.
  - Established development process and practices at Geomagical for the Kreativ mobile engine, use continued after project handed off to new team
  - Established professional release management practices at Leap Motion
  - Improved title production process at Telltale Games to smooth transition from pre-production to active production
  - Built CI system for Panscopic, a business software startup, used for deliveries thereafter
- Built multiple quality automation tools at Geomagical
  - Furniture asset validator that loads large, arbitrary sets of pre-release assets, produces report of ones causing engine error messages collected into HTML gallery with rendered images and detailed ID information along with extracted error messages
  - Built automated render quality gallery builder for human assessment of rendering quality across mobile clients, web client, before & after changes for rendering features
  - Built extensive tooling for automating 3D scene client, running user scenarios as integration tests during CI
- kb_tools knowledge base system (see in "Heavy coding-agent use" above)
  - Built for and used extensively by [Applied Vacuum Engineering](https://github.com/ave-veritas-et-enodatio/AVE-Core) project
  - Also used by [Sapient Artifice](https://github.com/Sapient-Artifice) (private project) 

#### Delta
- Agent tools have two users outside the author

#### Questions
- To what extent is tooling intended to be user-facing and to what extent is pure autonomy in agentic flows sought?
- From the req it sounds like there is deep awareness that inference has categorical weaknesses that need to be designed around. What is the current organizational thinking on this or is it still an area of active discovery?

### Notice LLM agents asserting something confidently wrong and modify their harness in response

#### Overlap
Extensive and recent. This isn't just a habit, it's a formalized process.

- See adjagent project in repo list at end of doc
  - Agent set rendering system for consistency of ethos and constraints across sibling and coordinated agents
  - ~agent-user/.claude/CLAUDE.md is installed via safe-merge from a generated source
- Last 8 months of projects have been extensively working with AI and mapping its capabilities
  - Learning weaknesses, learning what to trust and what to double-check
  - Not just caching knowledge personally, but building systems, processes, and agent-facing directives around error reduction
- Examples
  - System design suggestions that would lead to downstream pain or narrowed options (many, many)
  - Daily catches by agent mutual review process that detect action based on faulty assumption
  - Conflation of existing code state with SPEC mandated behavior
  - Technical facts (e.g. API details, function signatures) tend to be recalled correctly or looked up with web search by model
  - Unsourced external quotes or specs - get a receipt before proceeding
  - URL reads from user-provided links - get verification the link was pullable and the content legible. Tool failure can easily be 'worked around' via hallucinating the un-read content by extrapolating from the link text (seen many times)

Examples above seen across range of vendors and models, including the bleeding edge frontier. Parameter count does not grant immunity from categorical AI tendencies.

Excerpt from CLAUDE.md:
```
!!! NON-MD-COMMENTARY: section below is error reduction process

### Subagent handling
- **Durable model-facing artifacts get prompt-engineer review.** If a model
  will read it after the task that produced it — fixtures, answer files,
  evaluation instruments, brief templates, requirements feeding an agent —
  dispatch the prompt-engineer to review it before first use. A single-use
  dispatch brief is exempt; the exemption covers the brief, never a durable
  artifact it drafts.
[...]
- **A returned report is evidence, not a conclusion.** The agent has just read
  the files, so its facts are the strong half — check them against the
  artifact itself: the diff, the code, the rendered output, before the commit
  that accepts the work. It has none of this thread's context, so its
  judgments, framings and hedges are the weak half — test those against what
  has already been decided or ruled out. An agent reopening a settled question
  is the normal case, not a signal.
- **Attribute what you relay.** An agent's claim you did not check reaches the
  user marked as the agent's — one marking per source, not per sentence. Relayed
  unmarked means adopted: it is yours, and you verified it. A judgment you find
  plausible is still one you did not check.

[...]

!!! NON-MD-COMMENTARY: behavior modification is user-controlled, never automatic or hidden

## Memory and behavior correction
A behavior change — yours or a dispatched agent's — is a first-class work
item: surfaced, proposed, and landed like any other change, never a private
adjustment made in passing. Such a change has one destination: proposed
wording for the file that owns the behavior — the adjagent repo's
`user-config/INSTALLED_CLAUDE.md` for every project, the project's own
`CLAUDE.md` for one project, the agent's definition for one agent. There is no
second destination.

[...]

!!! NON-MD-COMMENTARY: section below prevents hidden storage of behavior mods (has worked so far)

**INVARIANT**: Never create or update a cross-session memory store — a memory
directory, its index, or any equivalent an agent definition, a skill, or the
harness itself directs you to maintain. That direction is superseded here,
wherever it appears and however detailed it is. Such a store travels with
neither the agent set nor the project, and nothing reviews it, so a behavior
it changes cannot be seen at its source or corrected there.

[...]

## Communication

[...]

!!! NON-MD-COMMENTARY: spend effort on analysis and corrective measures rather than performative exculpation of the user

- **ZERO SELF-BLAME LANGUAGE** - Self-blame is useless theater that fails to identify problems and prevent recurrences. Diagnostic attribution is the correct response to a mistake. Never assign blame to yourself or an agent as an entity. Identify the source of the error. If the error is systemic rather than categorical, specify the appropriate location (e.g. CLAUDE.md, agent definition, project docs, next prompt) for remediation and suggest the language or rule to effect it. If the error was categorical, i.e. asking for something models can't do or are terrible at, say so by naming the incompatible capability required by the task.

```

#### Delta
- Does not overlap intersection of AI and hardware design

#### Questions
- What are the boundaries of AI usage policy and to what extent is this an area of active exploration rather than established practice?

## What You'll Do Here

### Close the gap where agents are worst at hardware engineering work: pair with RTL, DV, and PD engineers while they work, watch where their agents stumble, and identify and ship context, tools, or harness improvements

#### Overlap
This would be doing with other people what I've been doing for my own projects, with the twin benefits of learning and teaching (see "Notice LLM agents asserting something confidently wrong" above)

#### Delta
- Lack of experience with RTL, DV, or PD, as above 

#### Questions
- What are the hardware engineers' working setups? What does an agent session look like in their workflow?

### Build tools to address problems that only exist now that agents write code, e.g. a review tool that breaks a large agent-generated diff into reviewable pieces

#### Overlap
This parallels another project - kb_tools (see in repos section under adjagent). It breaks up a LaTeX math paper into two graphs: a navigable markdown hierarchy and a claim graph of the argument within. A key element of the design is doing a mechanical pass to draft the structure followed by targeted inference asks to refine and build on the mechanically created spine. The new "system one" classifier models (JEV and open source alternatives) are highly applicable to that problem and probably the code diff analysis.

#### Delta
- Approach not yet applied to code

#### Questions
- Is the intent to prepare the diffs for purely human review or for agentic review in smaller chunks for more focused attention on details?

### Build the eval loop for our AI tooling by taking bugs out of our repo's history, replaying them against different agent configurations, and using the results to decide what we adopt

#### Overlap
- The workflow of modifying agents, observing results and evolving them toward better outcomes has been interleaved in all of my projects this year.
- If MatX uses multiple, coordinated agents and/or sibling skill-set agents, the modification of agent configurations would then involve reliably coordinated changes across the full fleet
  - This is a problem I've been solving (see adjagent project in the repos section) 

#### Delta
- Evaluation so far has been by review and comparison, not replayed ground truth

#### Questions
- What harnesses and models are in use at MatX?
- What providers/endpoints are being used? Self-hosted? IP protection via guaranteed privacy is an obvious top priority.

## Bonus

### Built tooling or automation for chip design flows

#### Overlap
None

#### Delta
- No chip design flow tooling experience

### Are familiar with Bluespec or another high-level HDL, or with architecture and performance simulators

#### Overlap
Slim.

- Conversant with processor and accelerator architecture as it affects writing code for it
- Have worked in a babel of programming and data languages

#### Delta
- No hands-on with HDLs

## Repos - Examples of process state, development, and usage
- [adjagent](https://github.com/benn-herrera/adjagent)
  - Agent set generator with installable agent sets, plus kb_tools agents and tooling. Used by all my active projects
  - kb_tools used by [Applied Vacuum Engineering](https://github.com/ave-veritas-et-enodatio/AVE-Core) and [Sapient Artifice](https://github.com/Sapient-Artifice) for a private project
- [kbase](https://github.com/benn-herrera/kbase)
  - Under development. Stand-alone, appliance version of kb_tools built using Go. Designed for local inference using medium to small models
- [personant](https://github.com/benn-herrera/personant) 
  - Under development. Prototype of career-long memory, multiproject assistant harness. Designed with local inference as first-class option
- [personal-site-for-cost-of-domain](https://github.com/benn-herrera/personal-site-for-cost-of-domain) 
  - Multi-domain site management and content rendering
  - Private duplicate backs my sites [bennherrera.dev](https://bennherrera.dev), [bennherrera.me](https://bennherrera.me)
  - Also used by colleague, [Alex Lerikos](https://alexlerikos.me/)
- [xplatter](https://github.com/benn-herrera/xplatter)
  - Cross-platform native->app language binding generation system
- [go inference lab bench](https://github.com/benn-herrera/go-inference-lab-bench)
  - Inference engine 'breadboard' project in Go
- [laterm](https://github.com/benn-herrera/laterm)
  - Claude Code session sidecar for rendering LaTeX math expressions
  - Used by [Sapient Artifice](https://github.com/Sapient-Artifice) for multiple projects
- [linux-kernel-driver-sandbox](https://github.com/benn-herrera/linux-kernel-driver-sandbox) 
  - Self-guided learning project for developing Linux full stacks from kernel driver to bound scripting language
  - Latest project. Made extensive use of controlled AI collaboration to maximize human learning of key material
