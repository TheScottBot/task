**To:** Dana Whitfield, Meridian Capital
**Subject:** Positions feed sample: validation results and next steps

Hi Dana,

Thank you for the sample export and the field notes; they made this quick to work
through. We have run the file through our validator, and the per-file report is
attached (the `.summary.txt`, with the full JSON report alongside).

**Headline:** 16 of 25 rows would land today. The 9 that would not are all
fixable at source, and none points to a problem with the file format itself.

**Blocking: rows we did not ingest**

- **src-1007 appears twice** with different NAVs (3,298,800.00 and 3,301,100.00), and
  there is no src-1008. As agreed with Arseniy, we rejected both rather than pick
  one. Could the second row be src-1008 with a mis-keyed ID?
- **Row 12 has no `source_row_id`** (account MC-44098, North Haven VI), so it cannot be
  keyed for your audit trail.
- **src-1011 has a negative NAV** (-42,100.00).
- **src-1015 and src-1017 are Closed with a non-zero NAV;** flagged, not ingested, as
  you asked.
- **src-1019 has no currency;** rejected rather than defaulted, as agreed.
- **src-1004 and src-1020 use a slash date** (`03/31/2026`). Without knowing whether
  your system writes these month first or day first we would be guessing, so we
  reject and flag them rather than risk a wrong valuation date.

**Landed, but please confirm**

- **src-1016 is in EUR.** Is that intentional, and how should NAV be reported for
  non-USD positions?
- **src-1010 has a commitment of `N/A`;** we set it to 0 as you described.
- **src-1013 and src-1023 use a written month** (`31-Mar-2026`). There is no ambiguity
  there, so we normalised them to ISO.

**Questions**

1. Can you confirm the export always writes slash dates one way, for example month
   first? If so we will normalise them safely; ISO at source would be better still.
2. You mentioned five funds in this batch; we count seven. Could you confirm the list?
3. Share class: splitting it from the fund name works fine on our side, but a
   separate `share_class` column would remove the guesswork. Is that easy to add?

**Next steps**

- **Meridian:** correct the nine rows, answer the questions above, and re-send.
- **Tangible:** re-run the corrected file within one working day and confirm a clean
  reconciliation before we plan the second batch.
- **Together:** SFTP suits us; if the export can write to a temporary name and rename
  on completion, we will never read a half-written file.

Kind regards,
Scott
