# Meridian Capital — Positions Export: Field Notes & Requirements

*From: Dana Whitfield, Integration Lead, Meridian Capital*
*To: Tangible integrations team*

Hi team — here's the sample export from our portfolio accounting system and the
notes you asked for. This is roughly the shape of the nightly file we'd drop to
SFTP (we're open to an API push instead if you prefer — discuss).

## Field notes

| Column | Meaning | Notes from our side |
|---|---|---|
| `source_row_id` | Unique row ID from our system | Should be stable day to day for the same position. Occasionally a row gets re-exported with a correction — latest file wins. |
| `account_id` | Our internal account number | One account can hold many positions. This is NOT the end client's name. |
| `account_holder` | Display name of the investing entity | For your UI; don't key anything off this. |
| `fund_name` | Fund name as we display it | Note: for our own funds we append the share class (e.g. `Meridian Growth VI - Class A`). I believe your model wants share class as its own field. |
| `vintage_year` | Fund vintage | |
| `commitment` | LP's total commitment | Should always be a positive number; if it's blank or non-numeric that usually means the fund is commitment-free (secondary purchases) — treat as 0 but flag it for us, we want to fix those at the source. |
| `nav` | Position NAV as of `nav_date` | Comes from the fund's latest quarterly statement. |
| `nav_date` | As-of date of the NAV | Format should be ISO but I've seen the legacy system emit other formats on some funds — normalizing on your side is fine. |
| `currency` | ISO 4217 | Almost always USD. |
| `status` | `Active` or `Closed` | A `Closed` position should have NAV 0 (fully exited). If you see otherwise, it's a bug on our side — please flag rather than ingest. |
| `advisor_email` | Covering advisor | Used for notifications in your platform. |

## Our requirements / asks

1. Positions land in Liquidity Hub keyed by `source_row_id` — our compliance
   team wants a clean audit trail from your platform back to our system.
2. Re-deliveries and corrections happen; your side should never double-count
   or duplicate a position.
3. Advisors should only see positions for accounts they cover (we can discuss
   how coverage mapping gets to you — separate feed, later phase).
4. We'd like a per-file summary back (accepted / rejected / warnings) — email
   is fine for now, a webhook later.
5. First fund batch: the five funds in this sample. Second batch (~40 funds,
   ~100k positions) follows once the first batch reconciles.

One open question from our side: we append share class to the fund name today.
If that's painful for you, tell us what you'd rather receive and I'll check
what the export job can do.

— Dana
