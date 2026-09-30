# MatX AI Tooling / Benn Herrera Fit

[Benn Herrera](https://bennherrera.me)'s self-assessment of experience applicability to the problem space and requirements for the role of [Infrastructure Engineer, AI Tooling](https://jobs.ashbyhq.com/matx/f63c692f-297c-4bf1-955d-cc0e808289bf).

Authorship note: This document was hand-authored. AI was used for review, but the content is mine. -bph

## Core Requirements

### Run production infrastructure somewhere dynamic; know which shortcuts you'll regret

#### Overlap
Significant overlap

- Geomagical 3D asset processing pipeline team
  - Switched from stable graphics engine project to asset pipeline to help address significant overloading
    - High demand on team for large volumes of furniture model processing (get it in the catalog ASAP!)
    - Significant reliability issues with the pipeline itself 
  - Initially tasked with individual module optimizations, identified brittle, unsafe conditions
    - No ability to test from branches under deployed conditions before pushing live images (high DOA deployment rate following PR merges)
    - Use of extremely out of date containers and software, limiting improvement paths
    - Updated OS images and software packages, introduced image build-time testing, greatly reduced DOA deployments
      - Imperfect solution, container build nodes were not exact match for deployed nodes, but it was a pragmatic improvement
      - The right solution came next 
  - Identified Dagster + Celery pipeline coordinator as key pain point - our use patterns did not match its offering
    - Normalized to invisibility, earlier effort to convert to Temporal made a good start, but stalled due to platform team saturation
    - Near daily breakages interrupted key processing jobs, required busy platform engineer to "turn it off and back on again"
    - Took up the conversion effort, coordinated with teammates, accommodated in-flow feature work to ensure continuity under both coordinators
    - Drove it to completion, eliminating near-daily interruptions of key staff
    - With Temporal conversion came ability to test under deployed conditions on pre-merge PR branch
    - A long-cut I very much did not regret
  - Did actually get those module refactors done
    - Stabilized, optimized, sanitized - as much as 8X speedup in some
    - Eliminated fragility and maintenance opacity in others
- Some heuristics for regrettable shortcuts
  - The engineer's version of the trial lawyer adage "never ask a question you don't know the answer to" - never cut a corner that interferes with knowing exactly what will happen before pushing the big, red "deploy" button
  - Anything that prevents visibility into what is actually happening after you've deployed ("It's not working right, and I have no idea why" is a terrible place to be)
  - Anything that interferes with a minimum time control loop ("It's broken and we have the fix but it will take an hour for it to actually deploy" is another terrible place to be)
  - Anything that prevents instant-response mitigation of problems ("If I had only followed through on adding remote feature switches the fire would be out right now...")
  - "This C library seems to do what we need and probably won't crash in the target environment. It'll be fine..."

#### Delta
- Trial by fire exposure to platform infrastructure systems, but was not key focus for an entire position

#### Questions
- How built out is the infrastructure now? What is intended and how will this role participate?

### Heavy coding-agent use; strong opinions on what to let them do, what not, and how to verify their work

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
- Agent harness used exclusively within sandbox. An unprivileged agent user runs all harness processes - see "Sandboxing" section below
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

### Built engineering workflows (methodology, flow automation, review tooling, agent harnesses) that others adopted and kept

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

### Notice LLM agents asserting something confidently wrong; modify the harness in response

#### Overlap
Extensive and recent. This isn't just a habit, it's a formalized process.

- See adjagent project in repo list at end of doc
  - Agent set rendering system for consistency of ethos and constraints across sibling and coordinated agents
  - ~agent-user/.claude/CLAUDE.md is installed via safe-merge from adjagent/user-config/INSTALLED_CLAUDE.md (see sandboxing section below)
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

Excerpt from agent-user ~/.claude/CLAUDE.md:
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
- None outside of reqs not visible from job posting

#### Questions
- What are the boundaries of AI usage policy and to what extent is this an area of active exploration rather than established practice?

## Bonus

### Operated Bazel remote execution or a remote cache
Tangential, not directly on point.

#### Overlap
- Extensive use and authoring of build systems across platform, OS, and vintage: Make, CMake, Gradle, Swift PM, MSBuild, more
- Used and modified containers for CI builds

#### Delta
- No actual Bazel usage

#### Questions
- Is there a blend of build and revision control systems in use?
- Would agents be expected to be allowed to modify containers or CI processes?

### Sandboxing and ephemeral compute for untrusted workloads

#### Overlap
Significant and recent.

- Set up unprivileged agent-user, agent-group on macOS
  - Agent-user has umask that makes all files group-writable
  - All harness processes are launched by this agent
  - Zero paths to executing as privileged user outside of active hacking (nothing is 100% secure)
  - No paths on machine are writable to agent-user outside of /tmp, its home dir, and dirs given to it for coop work
  - Agent-user possesses no ssh keys or access to repos not cloneable via public https://
  - Primary user added to agent-group, all collaborative work done under agent-user owned directory
  - Primary user uses agent-user shell for all coop tasks not requiring higher privs. Does repo clone/pull/push via privileged shell.
- Professional experience with Docker and containerization
  - Deployed containers used for CI builds
  - Model asset processing pipelines with containerized stage execution coordinated by Temporal
  - Local execution of container images to preview deployed behavior
  - Container image construction-time testing to reduce DOA deployment risks
- Personal project experience with containerization and virtual machine targets
  - Linux device driver sandbox project (see repo list at end of doc) used podman container for Linux kernel build and staging, QEMU virtual target
- Comprehension of containerization/virtualization risks and trade-offs - a few highlights:
  - If guest machine is same CPU architecture, near-native speed. Emulation of non-native CPU incurs significant performance penalty
  - 'Containerized' != 'Bulletproof' - a writable mounted host partition can still get nuked by a mishap running on the guest, especially a mishap running as guest root
  - Passthrough access to critically useful hardware, like accelerators, can be tricky, fragile, time consuming to set up and keep working

#### Delta
- Have not used containers as sandboxing strategy (deliberate choice for own personal use machine)

#### Questions
- What platforms and virtualization apps need to be supported? All Linux? macOS? Windows?
- Is the focus entirely on infrastructure or will approaches be used on developer and/or researcher local work machines?
- To what extent does the device-access-from-container-guest issue come into play?

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
  - Self-guided learning project for developing Linux full stacks from kernel driver to bound scripting
  - Latest project. Made extensive use of controlled AI collaboration to maximize human learning of key material
