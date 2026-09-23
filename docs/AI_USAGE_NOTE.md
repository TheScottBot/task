# AI usage note

- **Tool:** Claude Code (Claude Opus 5.5) in the Claude desktop app, working from a
  specification I wrote beforehand that applies my engineering datum by reference.
- **Used for:** reading the assignment, the client's field notes and my reference
  implementation (ftrio-python) in full before any code; writing the test suite
  first, then the implementation; drafting the README, decision records and the
  email to Dana for me to edit.
- **Kept for myself:** the specification, the validation table and every judgement
  call. Before building, the assistant raised eight blocking questions (date
  formats, input bounds, exit codes and so on), each with options and a
  recommendation; I answered all of them before it wrote a line.
- **Where I corrected it:** its first reading of rule R5 followed my spec's list of
  required fields, which I had written too narrowly; it flagged the gap and I
  widened the rule. I also stopped it proposing commit messages: every commit is
  mine. And I overrode its date recommendation: it proposed reading slash dates
  month first wherever only one reading was a real day, but I won't guess a date,
  so every slash date is rejected and flagged until the client confirms the convention.
- **How I verified it:** every one of the 25 sample rows has its expected decision
  and findings pinned in a test. Fifteen deliberately planted faults, six of them in
  the date handling, were each caught by the suite; the one first missed (a store
  failure mid-ingest archiving the file) exposed an untested path, so a test was
  added before moving on. Green tests were not the end of it: running the README
  steps for real, twice in quick succession, caught an archive name collision the
  suite had passed. The first design refused to overwrite, which was safe but left
  the file in the drop folder, the very thing archiving exists to prevent; a
  same-second archive now takes the next free name and nothing is overwritten.
