# Take-Home Assignment: Client Positions Feed Onboarding

**Timebox: 2 hours.** We'd rather see a complete, smaller solution than an
ambitious fragment. Use any language, frameworks, and tools you like —
**AI assistants are explicitly permitted and expected**. We care about how you
use them, not whether.

## Background

Tangible's Liquidity Hub is a multi-tenant platform where enterprise clients
(large wealth platforms, private banks) let their advisors and LPs list, bid on,
and transfer positions in private-market funds.

A new client, **Meridian Capital** (fictional), wants to onboard. Their
integration lead, Dana, has sent over:

1. A sample of their nightly positions export: `sample-positions-feed.csv`
   (~25 rows, LP positions in private funds).
2. Their field mapping notes and requirements: `client-field-mapping.md`.

This is the first technical exchange of the engagement. In the real world, what
happens next is: we validate the feed, find the problems before they do, and
send a reply that builds their confidence in us. That's exactly what you'll do.

## Part 1 — Feed validation & ingestion service (~60–75 min)

Build a small service (or CLI + minimal API — your call) that:

1. **Ingests** the CSV feed and maps it to a canonical position model of your
   design (the mapping doc explains what each client field means).
2. **Validates** the data and produces a structured report of every problem it
   finds. Decide — and be ready to defend — which problems should *reject* a
   record, which should *warn*, and which can be *auto-corrected*.
3. **Is safe to re-run**: the client's export job sometimes re-sends the same
   file. Re-ingesting must not create duplicate positions, and conflicting
   re-deliveries must be handled deliberately, not silently.

Deliverables for Part 1:

- The code (a repo folder or zip), with a short README: how to run it, and your
  design decisions in ~10 bullets max.
- A sample validation report produced from the provided feed.

## Part 2 — Client follow-up email (~20–30 min)

Write the email you would actually send to Dana (Meridian's integration lead,
technical but not an engineer on our platform) after running your validator.
It should:

- Summarize what you found, prioritized by what blocks onboarding
- Ask the clarifying questions you genuinely need answered
- Propose concrete next steps on both sides

Tone matters: this is the first impression with a new enterprise client.
200–400 words. Attach/reference your findings as appropriate.

## Part 3 — AI usage note (5 minutes, ~5 bullets)

Briefly: which tools you used, what you used them for, and one place where you
overrode or corrected what the AI gave you (or would have, if it didn't come up).

## What we're evaluating

- Does the validator run, and does it find the real problems in this feed?
- Judgment: reject vs warn vs auto-fix, dedup/conflict handling, data model design
- Communication: accuracy, prioritization, tone, quality of your questions
- How you use AI: verification and judgment, not copy-paste

## Ground rules

- Don't build auth, a UI, deployment, or a real database unless you have time
  to spare — an in-memory or SQLite store is fine.
- The feed is small on purpose. Assume it represents a real 100k-row nightly
  feed, and be ready to discuss what you'd change at that scale (in the debrief,
  not in code).
- Questions during the assignment window: email us as you would Dana — it's all
  signal.
