# Engineering datum

Version 2, dated 20 September 2026.

The rules and guardrails for specification driven work between an author and a
coding agent.

This document is generic. It names no project, no device, no product and no
language runtime. A project specification applies it by reference and adds only
what its subject requires.

Two roles run through it. The **author** owns every decision, every commit and
every claim that rests on hardware or on their own observation. The **agent**
does the reading, the writing, the building and the testing, and says plainly
what it did, what it did not do, and why.

## Applying this datum

A project specification **MUST** state, in its opening:

- the version of this datum it applies, by number and date
- which optional modules in Part 4 it applies, and which it does not
- what its subject requires beyond this datum

**MUST NOT** restate a rule from this datum inside a project specification. A
restated rule drifts from the original and then two documents disagree. Reference
it instead.

**MUST NOT** silently depart from a rule here. A project that genuinely cannot
meet one records the departure in `IMPLEMENTATION_DEVIATIONS.md` with the rule,
what is done instead, the reason and the author's decision, exactly as a contract
deviation is recorded.

This datum is versioned because it changes. A specification naming version 2
means version 2, and a later version does not silently apply to work already
planned against an earlier one.

## Reference implementations

Where this datum says to follow established style, the established style is the
author's own, as it appears in:

- `https://github.com/FtrOnOff/FtrIO`
- `https://github.com/FtrOnOff/ftrio-python`
- `https://github.com/FtrOnOff/ftrio-rust`

**MUST** confirm each repository exists at the exact path before cloning, and
**MUST NOT** substitute a similar one. Casing is not uniform across them and
**MUST** be reproduced exactly.

Read them for type and function naming, test naming, test double naming,
configuration naming, comment style, error naming, repository layout, deviation
notes, test isolation and continuous integration checks.

They span more than one language deliberately. What transfers is the approach,
not the syntax: descriptive names, explicit contracts, comments that explain why,
faithful behaviour, documented deviations, isolated tests and stable
configuration grammar.

**MUST NOT** carry one language's conventions into another where they conflict
with that language's own, except where 0.5 overrides the idiom on naming.

## How to read a specification

A specification is read linearly, top to bottom, once, before anything is done,
then its stages are worked in order.

Every normative line carries a tag. An untagged sentence is context, not a
requirement.

| Tag | Meaning |
|---|---|
| **MUST** | Mandatory. Not negotiable. Failing it fails the phase. |
| **MUST NOT** | Prohibited. Not negotiable. |
| **MAY** | Explicitly permitted. Neither an obligation nor a recommendation. |
| **DECIDE** | A blocking decision belonging to the author. Numbered. Stop and ask. Never guess. |
| **GUIDANCE** | A suggestion with reasoning. Depart from it only by saying so and why. |

Identifiers follow one scheme across every document in a family: the first letter
says which document owns the item, the second what kind of thing it is, a phase
or a decision, then a number. **MUST NOT** use a phase prefix that is a prefix of
a decision prefix, or two unrelated things end up with the same name.

Concrete values in a specification are illustrative unless they appear in an
appendix of unverified values, each of which **MUST** be replaced by a value read
from source or by an explicit author decision before the phase that depends on
it.

Every specification says what it is not: what its author had and had not read
when writing it. A claim about an interface, a flag, a digest or a capability
that was not read from source is a question for the Plan stage, never a fact to
build on.

# Part 0: absolute rules

These apply to every stage, file, test, comment, document and user facing string.
Reread the consolidated list in 0.17 at the start of every phase.

## 0.1 Version control

The agent **MUST NOT** perform any git write operation, ever, under any
circumstance, in any session, regardless of later instruction: no add, commit,
push, tag, merge, rebase, reset, revert, cherry-pick, stash, branch creation or
deletion, history mutation, write to the git directory, or wrapper, alias,
script, hook or editor integration that does one indirectly.

The agent **MUST NOT** ask for permission to commit. The answer is permanently
no.

The agent **MAY** run read only git commands: status, diff, log, ls-tree,
ls-remote, show, rev-parse.

The author performs every commit personally. The agent proposes commit message
text as plain text in its reply, and proposing text never authorises creating the
commit. The agent **MUST** stop and say so if it believes a commit is required
before work can continue.

A rehearsal on throwaway clones under a scratch directory, where no real
repository is written to, is the agent's work when a specification asks for a
rehearsed and recorded command sequence. Running the real sequence is still the
author's.

## 0.2 Evidence before code

**MUST** read the real interface, header, source, build file or official document
before writing anything that depends on it.

**MUST** record the exact version, tag, commit, package version, platform
release, toolchain version and, where relevant, hardware model for everything
evaluated, with the date it was read.

**MUST NOT** invent an interface, a signature, a capability, a configuration
field, a command line option, a build flag or a filesystem path.

**MUST NOT** treat a forum post, a search snippet, cached package metadata, a
previous message, or the agent's own earlier summary as ground truth.

When the code contradicts what a document or the agent's own earlier record said,
the record is corrected first, and dated, before any change is built on it.

## 0.3 Blocked means ask

When behaviour is ambiguous, underspecified, environment dependent or a judgement
call, **MUST** stop that phase and ask.

**MUST** phrase every question with all five parts:

1. the exact decision that is blocked
2. why the available evidence does not settle it
3. the viable options
4. the meaningful trade offs
5. the recommendation, explicitly labelled as a recommendation

**MUST NOT** ask about anything already settled in the specification.

**MUST** batch questions by the stage that needs them rather than sending them
one at a time.

## 0.4 Tests first

**MUST** write a failing test describing the required behaviour, confirm it fails
for the expected reason, implement the smallest correct change, run the focused
tests, then the full suite, then refactor only while green.

For a move rather than a change, the moved suite is the test. It **MUST** be seen
to fail from its new home before the sources follow, so the harness is proven to
run it rather than skip it.

For a new check, the check **MUST** be seen to fail on a deliberately planted
violation before it is allowed to pass on the real tree. An unproven check is
worse than no check, because it is trusted.

**MUST NOT** modify, weaken, skip or delete a test written in an earlier phase to
make a later phase pass. If a later phase genuinely invalidates an earlier test,
stop and raise it, naming the test, the behaviour that changed, and why.

Extending an existing test with an additional assertion is permitted. Editing or
removing one of its existing assertions is not.

Tests written after implementation do not satisfy this rule unless the
implementation is discarded and driven again from failing tests.

## 0.5 Language idiom and naming

**MUST** follow the conventions of the language being written: its formatter, its
linter, its standard library patterns, its error handling, its project layout and
its test framework conventions. Code should look native to someone who works in
that language every day.

The single override is naming.

**MUST** use verbose, self documenting names, including where the surrounding
language culture is terser. Where a language's idiom favours short names, this
rule wins and the departure is deliberate.

**MUST NOT** use `mgr`, `svc`, `util`, `helper`, `data`, `item`, `tmp`, `buf`,
`msg`, `cb`, `handle`, `process`, `run` or `execute` as a name, or `ctx` beyond a
platform imposed signature.

**MUST NOT** use a single letter name except a loop index.

**MUST NOT** rely on an implicit, positional or terse closure, lambda or callback
parameter. Name every parameter descriptively. Where a platform imposes an opaque
context parameter, name the cast local descriptively at the first opportunity.

**MAY** use `id`, `url`, `len` and the like where a platform signature imposes
them, and an error value named by the language's own convention in the check
immediately following it.

Where the idiom and the naming rule appear to conflict beyond this, the naming
rule wins and the conflict is worth a comment.

## 0.6 Comments

**MUST** explain why: why a bound exists, why a value is rejected, why a
reconnect discards state, why a security boundary exists, why an unusual
implementation is required, why a deliberate duplication is deliberate.

**MUST NOT** restate syntax or paraphrase a descriptive name.

## 0.7 Do not repeat yourself

**MUST** express a rule, a limit, a path, a wire value, a timeout or a displayed
string in exactly one place.

**MUST** share test fixtures and test doubles rather than reimplementing them per
file or per package.

**MUST NOT** duplicate a grammar between a parser and an encoder. Derive both
from one table.

**MUST** decide which layer owns a validation rather than duplicating it across
layers.

**MAY** duplicate deliberately where removing the duplication would couple two
things that change for different reasons, if a comment says so and why.

## 0.8 Prose and typography

These apply to every tracked text file: source, comments, test names, test data,
assertion messages, logs, documentation, proposed commit message text,
configuration descriptions and user facing strings.

**MUST** use United Kingdom and Irish spelling conventions.

**MUST NOT** use the em dash or the en dash character. Use a comma, colon,
semicolon, parentheses or a separate sentence.

**MUST** also scan for converter mangled hyphen runs, being double and triple
hyphens in prose, since a document converter turns dashes into those and they are
the same defect wearing a different coat. The only exemptions are a Markdown
table separator row and a command line flag token.

**MUST NOT** put quotation marks around a phrase in a professional document for
emphasis or distancing. Quotation marks are for quotation.

**MUST** run the scan in continuous integration over the whole tree, and fail on
any hit.

Vendored third party sources are exempt from every rule in this section. They are
kept verbatim under 0.13 and cannot be edited to satisfy a house style, so the
scan **MUST** exclude the vendored paths by an explicit list rather than by
pattern. Excluding by pattern eventually excludes something that is not vendored.

## 0.9 No placeholders

**MUST NOT** emit a command, script or configuration line containing a
placeholder such as an angle bracketed path, identifier or filename.

If a real value is needed and not yet known, **MUST** stop, ask for the output of
the preceding command, and then produce the command with the real value in place.

The one exception is a value that exists only on the author's screen, such as a
process identifier, which is named as such.

A grammar or a contract table is not a command and **MAY** name its fields rather
than show sample values. Prefer naming fields, because a sample value in a
specification becomes a real value in an implementation.

## 0.10 Untrusted input

For any code that receives bytes, text or structured input from outside its trust
boundary, in any language:

**MUST** bound every read by an explicit maximum length, checked before the input
is copied, parsed or stored.

**MUST** treat every byte arriving from outside as hostile, and parse it with a
parser that cannot advance past its buffer.

**MUST** take every bound from the contract's own table, never from the input
itself, and refuse rather than truncate when a bound is reached.

**MUST** reject unknown fields, unknown verbs and missing required fields
explicitly rather than tolerating them.

**MUST** check every operation that can fail and surface the failure rather than
continue.

**MUST** release every resource acquired, on every exit path including error
paths.

**MUST** build clean under the strictest warning, lint and static analysis
setting the language offers, with warnings treated as errors.

**MUST** keep every module of portable logic free of platform, driver and
operating system dependencies, so it builds and tests on a development machine
with nothing but the language toolchain. A check on imports or include lines
enforces it.

**MUST** run the parser under whatever memory and undefined behaviour analysis
the language provides, in continuous integration.

**GUIDANCE** Keep a fuzz harness on the parser, running in continuous integration
on every change rather than on a schedule. A parser is usually the smallest and
highest value fuzzing target a project has.

A memory unsafe language adds obligations beyond these. See Part 4, module A.

## 0.11 Contracts are sacred once accepted

**MUST NOT** rename, alias, normalise, reinterpret or silently improve an
accepted contract, configuration key, state name, verb, event name, status code
or wire value.

**MUST NOT** supply a silent default for a required field or value.

**MUST NOT** accept unknown fields.

**MUST** version breaking changes and record migration notes.

**MUST** document every unavoidable deviation from a contract in
`IMPLEMENTATION_DEVIATIONS.md` with a one line justification and a covering test.

Before a contract is accepted it is provisional and freely revisable, and
applying this rule to it is the wrong kind of discipline. Every change made while
provisional **MUST** be recorded with its reason, and that record is the argument
for the shape it settles into. The freeze is an author decision.

## 0.12 One owner per contract

A contract has exactly one owning repository, which publishes its definition.

Every other repository implements it, holds a copy of the definition byte for
byte, proves the copy equal to the owner's by a recorded digest, and generates
whatever it derives from that copy with a check that fails if the derivation and
the copy ever differ.

An implementer **MUST NOT** propose a change to the contract from its own
repository. A change is raised in the owner's repository as a version decision.

The side that owns meaning interprets. The other side reports what happened and
renders what it is sent. A component that self certifies its own guard is
trusting the untrusted side, so the final decision belongs to the owner, taken on
the values it receives.

Ownership is not build order. The implementing side **MAY** be built first, and
often should be, because a contract discovered against a real consumer beats one
designed against an imagined one. Where that happens the definition is drafted in
the consumer's repository and promoted to the owner's at the freeze.

Promotion is a review, not a file move. Check field by field that the owner can
actually supply the value, that no field exists only because it was convenient to
the consumer, and that nothing encodes a consumer specific detail. Record what
changed at promotion, and require the owner's implementation to read that record
before building against the result.

**MUST NOT** leave a promoted definition on a branch that may be discarded. An
implementation is disposable and may reasonably be developed on a branch the
author abandons. A contract another repository is already building against is
not.

## 0.13 Dependencies

Before adding one, **MUST** record: the behaviour it provides, why the standard
library or the platform is insufficient, maintenance status, licence, size,
platform support, security implications, test strategy and replacement cost.

**GUIDANCE** Prefer a small dependency set, but do not hand roll a security
sensitive protocol to avoid a dependency. Prefer a small, permissively licensed,
widely reviewed implementation.

Prefer a dependency that lives in the language's own ecosystem and mainline
tooling over one requiring an out of tree component, a vendor supplied driver or
a manually maintained patch. An out of tree dependency breaks on an upstream
release and is nobody's responsibility to fix.

Vendored code is kept verbatim, pinned by upstream tag and commit, with its
licence and a digest per file beside it. It is never edited: a fix goes upstream
or into a wrapper. Record digests of the bytes as the tree stores them and, where
the tree normalises line endings, the upstream form too, so both can be verified.

A one time migration tool that ships in nothing built is recorded with its
version and invocation and is not a dependency.

## 0.14 Destructive operations

Anything that deletes, rotates a credential, disconnects a client, ends a session
or mutates state outside the process is destructive.

**MUST** be explicit in the model, idempotent, logged without personal data,
tested for partial failure, and unreachable from a read only request.

**MUST** record the origin of a destructive action wherever more than one surface
can trigger it, as a required field rather than an optional one, so no path can
omit it and the record says which surface acted.

Before the agent deletes or overwrites a file it looks at what is there. It
**MUST NOT** delete ignored tool state it did not create without saying so, and a
fresh build directory is preferred to a clean.

## 0.15 Observability

**MUST** make faults visible rather than silent. A component that silently stops
working is worse than one that plainly reports that it has.

**MUST** count and surface rejected input by reason category, version mismatches,
retries, reconnections and resource limits reached.

**MUST NOT** log a payload, a credential, a token or personal data. Log the verb,
the reason category and a length.

**MUST** say what is being retried, once, and why. A correct retry that is silent
about retrying reads as a failure.

**MUST** make an absent optional subsystem observable at startup rather than
silent, so its absence is a fact in the log and not a mystery in the field.

**MUST** emit structured output rather than free text wherever anything will read
it programmatically.

## 0.16 Accessibility

Where a specification produces a human interface, of any kind:

**MUST** provide keyboard accessible controls, visible focus, sufficient
contrast, labels that assistive technology can read, and appropriately announced
state changes.

**MUST NOT** convey status by colour alone.

**MUST** respect a reduced motion preference where the platform exposes one.

**MUST** treat legibility under real conditions as a requirement rather than a
nicety, and say in the specification what those conditions are.

## 0.17 Consolidated prohibitions

Reread this list at the start of every phase. It adds nothing new.

Never:

1. Perform a git write operation.
2. Invent an external capability, interface, path, flag or option.
3. Guess a **DECIDE** item.
4. Write implementation before a failing test.
5. Weaken or delete an earlier phase's test.
6. Trust a check that has not been seen to fail on a planted violation.
7. Accept input without a length bound and a version check.
8. Expose a shell, an arbitrary command or a filesystem path through a contract.
9. Persist a secret to storage, including logs and crash dumps, or log a payload.
10. Queue an event across a disconnection and replay it later.
11. Encode the owner's meaning in the reporting side.
12. Hold authoritative state on the reporting side.
13. Rename or silently improve an accepted contract.
14. Use an em dash, an en dash or a converter mangled hyphen run in a tracked
    text file.
15. Emit a placeholder in a command or script.
16. Use a single letter name outside a loop index, or an implicit callback
    parameter.
17. Use real personal data, real credentials, real captured media or real
    customer payloads as fixtures.
18. Create a general end to end suite spanning two independently built sides.
    Substitute contract tests against a double on each side, plus whatever
    physical or manual checks the specification names.
19. Claim a gate belonging to the author has passed, or infer one from a green
    automated run.
20. Declare a phase complete on the strength of the agent's own environment
    alone.

# Part 1: stages

## Stage one, Plan

**MUST NOT** write implementation code or a behavioural test until the Plan stage
has settled the phase being implemented.

**MUST** produce `docs/evaluation/ACTUAL_CONTRACT_EVALUATION.md` recording, for
every item the specification lists: source, version or commit, retrieval date,
relevant files, what was observed, uncertainties, experiments performed,
conclusions accepted, and decisions still needing the author.

**MUST** read the reference implementations named at the top of this datum as
part of the Plan stage, and record what was taken from them.

Every claim in the record was read from source or run for real, and the record
says which. A question a real experiment can answer is answered by running the
experiment on a throwaway copy, never by reading documentation alone.

Plan stage exit: every value read from source or decided; every experiment
recorded; every decision answered or explicitly still open with the phases it
blocks, asked in the five part form, batched.

## Stage two, Execute

Each phase **MUST** begin by rereading Part 0, in particular 0.17.

Each phase **MUST** carry all five headings. A phase missing any of them is not
ready to work.

- **Work**: included behaviour
- **Excluded**: behaviour deliberately not built here, and why
- **Assumptions to verify**: beliefs that must be checked before being relied on
- **Tests first**: written and failing before implementation
- **Done when**: automated criteria, and, where relevant, an author gate

Automated criteria **MUST** be reproducible by the author on a clean machine with
no project specific hardware attached.

An author gate is anything only the author can clear: a physical device, a manual
acceptance, a judgement about how something looks, reads or feels. The agent
**MUST NOT** claim one has passed, and **MUST NOT** infer one from a green
automated run. A phase whose gate is outstanding is incomplete, but the agent
**MAY** proceed to a phase that does not depend on the gated behaviour, saying so
explicitly.

A phase's Excluded list is a hard boundary. What a phase finds that is not its
own to fix is recorded as a finding for the owner of that thing, with the likely
fix, and left.

## Stage three, Verify

At the end of every phase **MUST** output a reproduction report: exact commands
used, toolchain and platform versions, focused test result, full test result,
analysis and sanitiser results, warning count, tests skipped and why, tests
requiring the author, and any gate still outstanding.

**MUST NOT** declare a phase complete before the author reproduces the automated
criteria on a clean machine.

Every pull request **MUST** run: the prose and typography scan; a warnings as
errors build; the full test suite; whatever memory and undefined behaviour
analysis the language offers; a short fuzz run where a parser exists; the build
against every pinned platform target; and every tree wide check the specification
names.

Release **MUST** confirm: every **DECIDE** item resolved or explicitly deferred
with the author's agreement; `IMPLEMENTATION_DEVIATIONS.md` complete; supported
platform versions named; known limitations published; and a changelog that names,
per tag, any contract digest built against, every change to shared code since the
previous tag, and which gates were cleared at which commit.

# Part 2: required documents

Every repository, and every product directory within a repository holding more
than one, carries the documents marked always.

| Document | When | What it holds |
|---|---|---|
| `README.md` | always | what it is, how to build it from inside its directory, where it came from |
| `TESTING.md` | always | every suite with its command and where it runs; testing deviations with their reason; author gates |
| `IMPLEMENTATION_DEVIATIONS.md` | always | every departure from a contract, from the project specification, or from this datum: the rule, what was done instead, why, the author's decision, the covering test |
| `CHANGELOG.md` | always | per tag, as Stage three requires |
| `LICENSE` | always | the licence and holder |
| `docs/evaluation/ACTUAL_CONTRACT_EVALUATION.md` | always | the Plan stage record, every phase's findings and reproduction report |
| a contract document | when a contract exists | references the definition in its owner's repository; states what this directory holds and what it holds elsewhere; never restates the definition |
| `SECURITY.md` | when there is a trust boundary | the threat model, the accepted risks in the author's own words, and the limitations stated plainly rather than implied |
| `HARDWARE_COMPATIBILITY.md` | when there are author gates on hardware | what has been run on what, by whom, with the date; only the author adds a row saying a gate was cleared; measurements owed and their status |
| `FIELD_NOTES.md` | when there is real world use | what real use showed, dated |
| `PROVENANCE.md` | when code is imported or vendored | where every file came from: repository, commit, digest; written once at the import and once per extraction, after which the repository's own history is the provenance |
| `PRIVACY.md` | when personal data is handled | what is collected, what is not, retention, and what the software does not protect against |

A phase record is history and **MUST NOT** be rewritten as if the past did not
happen. A later change to what it describes is a dated parenthesis or a dated
note. A layout table, a rule or a guidance paragraph that states the present is
rewritten outright.

# Part 3: working practices that earned their place

- A change that a rule requires and that the tools can express becomes a check in
  continuous integration, not a sentence in a document.
- A check is proven against a planted violation before it is trusted.
- A host tool that touches the operating system keeps its decisions in a pure
  module the tests can reach, and the shell prints what the module returns.
- Tool state lives under the directory that uses it and is ignored there. A fresh
  checkout recreates it by the documented command, and nothing in version control
  depends on it.
- Keep checkouts at short paths on platforms with path length limits, and name
  toolchain directories by version rather than by archive name.
- Stale build output from another machine or architecture is a trap for a
  reproduction report. Prefer a fresh build directory to guessing.
- A finding made on the way to a phase's goal is recorded with its evidence where
  it was found and raised to its owner. It is fixed in the phase that owns it,
  with its own test, not in passing.
- When the author's word is the only evidence for a gate, the record says so in
  those words, and says what was and was not written down.
- Everything the agent reports is what happened. A failing step is reported with
  its output, a skipped step is named as skipped, and a step that was verified is
  stated plainly.
- A specification that has to be read twice to find a rule has the rule in the
  wrong place.

# Part 4: optional modules

These are not part of the datum by default. A project specification applies one
by naming it, and says why.

They live here rather than in a project specification because more than one
project needs them, and because the alternative is each project inventing its own
version and drifting.

## Module A: memory unsafe languages

Applied when the project is written in a language without memory safety.

In addition to 0.10:

**MUST NOT** use an unbounded copy or format function of any kind.

**MUST NOT** allocate on the heap in any input handling path. Size buffers once,
at start, from a bound in the contract's table.

**MUST** link every test binary with the allocation functions wrapped, so a test
can prove the code under it did not allocate.

**MUST** check every allocation and release every resource on every exit path,
including error paths.

**MUST** build warning clean under every target's real flag set, not only the
development machine's. A warning clean host build proves nothing about a target
whose toolchain differs in a code generation default. The cheap approximation is
a host build under each target's warning flags, optimisation level, defines and
ABI defaults, and the real target builds remain the proof.

**MUST** run every host test under the address and undefined behaviour sanitisers
in continuous integration.

**MUST** keep a fuzz harness on the parser in continuous integration under the
sanitisers, on every change rather than on a schedule.

## Module B: a repository holding several products

Applied when two or more products implement one contract and share code.

- `shared/` holds what every product builds: the contract library, the copy of
  the definition and its digest check, the generator, the fuzz harness, the test
  harness, the development stand in for the other side of the contract, and any
  logic with no display, no input model and no platform in it. It depends on
  nothing in any product.
- Each product directory is that product and nothing else: its specification, its
  required documents, its build entry point run from inside its directory, its
  tool state ignored under its directory, its identifiers unchanged by the move.
- Products depend on `shared/` and on nothing in each other, proven by a check on
  import or include lines.
- Each product builds `shared/` by relative path and by no other means. No copy.
  A symlink only where the build tool cannot follow a relative path, recorded as
  a deviation with its platform cost.
- Each product's build excludes the shared tests, fuzz harness and stand in,
  proven by the artefact naming no object, archive member or symbol from them,
  and by the artefact not growing across the extraction.
- The shared modules are separable: one build target per module, so a product
  that needs fewer takes fewer.
- The shared code defines nothing and encodes no product's meaning. A product
  specific choice is injected through a surface supplied at initialisation,
  testable on the host against a table of fake products, and lives under that
  product's directory with its deviation record pointing at the injected
  function.
- What shared code owns is tested once, under `shared/`, against fake products.
  What each product owns is tested under that product.
- Every product's continuous integration job runs the shared suites again under
  that product's own host flag set, and the shared job builds every shared source
  under every product's flag set approximated on the host.
- One commit names the state of everything: a gate cleared on any product names
  one commit of the tree.
- **MUST NOT** hold two copies of any file. What more than one product needs
  lives in one shared place and nowhere else, and a check in continuous
  integration fails on any same named, same content file elsewhere.

Importing an existing repository into such a tree keeps every commit, rewrites
every path under the product directory, and is proven by the rewritten tree's
blob hashes equalling the source's, by commit metadata equalling the source's,
and by following a moved file's history reaching a commit older than the import.
The old repository is retired only after its product's gate has been cleared from
the new tree, with a note at the top of its README naming the new repository, the
directory, the import commit and its own last commit, and is then archived read
only.