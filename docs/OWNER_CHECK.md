# THE OWNER CHECK — how to validate a report without being a data person
*(5 minutes per report, no math required. This is the standing "owner
reviews every report before it ships" law, made doable.)*

## The one idea to hold

You are not re-doing anna's math — she already validated her own
claims harder than you could by hand. Every comparative claim was
re-tested on 200 random half-samples of the data (that's what
**SOLID / WEAK / UNSTABLE** means), every number traces to a receipt
in the same file, and anywhere the data couldn't support a claim she
said REFUSED instead of guessing. **Your job is the one thing she
can't do: know what the client's business is.** A machine can verify
that east region = 284,853; only you can notice that a coffee cart
should not have $95M in revenue — that smell means a column was
misread, not that the math is wrong.

## The checklist (in order, every report)

1. **Read the headlines out loud.** Would any of them make the client
   laugh? Impossible sizes, categories that aren't real, a "top
   customer" that is obviously a supplier. Nonsense here = a column
   was misread at intake → don't ship, rerun or ask for help.
2. **Check "What is in this data".** One line per column. Does each
   description match what the client said the file is? The two that
   matter most:
   - the money column shows dollar totals (if it says "text,
     profiled only" on a price column, intake failed — don't ship);
   - the date range matches what the client sent (a 2019 file
     claiming 2026 dates = wrong column picked as time).
3. **Read the normalization notes** (top of the report). This is the
   list of everything changed at intake: quarantined rows, converted
   currency, blanked missing markers. If more than ~5% of rows were
   quarantined, the client's file has a problem — tell them, that's
   a finding they'll pay for.
4. **Spot-check ONE number.** Pick any headline number, scroll to the
   receipts at the bottom, find it there. It will be there — the
   report is built so every sentence traces. If you ever can't find
   one, do not ship; that's a bug worth more than the gig.
5. **Respect the grades.** To the client: SOLID claims can be stated
   as findings; WEAK/UNSTABLE keep anna's own hedged wording, never
   upgraded to sound better. A REFUSED is a real answer — "the data
   can't support that claim" is something clients pay to know.
6. **Never edit a number by hand.** If something looks wrong, rerun
   or file it. One hand-edited number and the guarantee ("any
   unreceipted number = free revision/refund") becomes a lie.

## The wording that ships with every report

- Disclosure (always): built with proprietary deterministic analysis
  software, human-reviewed; not an LLM writing numbers.
- Guarantee: any number that doesn't trace to a receipt = free
  revision or refund.
- Privacy: client data stays local, never enters any learning
  system, deleted on request.

## When to stop and ask

Anything you can't trace, anything that smells wrong after step 1,
any error message you haven't seen before. A skipped report costs a
gig; a wrong shipped number costs the reputation the receipts exist
to build.
