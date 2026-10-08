---
name: testing-comments
description: Write a Testing comment on a pull request, recording what was run beyond CI and what the results were. Use after regridding real or synthetic data, inspecting output, or running the tests locally for a PR.
---

# Testing comments

What you ran that CI does not, and what came of it.

CI already runs the whole suite on Linux and macOS, against both the
newest and the oldest dependencies, and builds the docs with `-W`. The
reader can see those checks. Do not report them again.

- Say what you ran and on what, in one sentence: the command, and the
  archive or files it read, on NIRD or a local copy.
- Say the result: how many experiments passed, or the log lines that
  matter. If you looked at the regridded output, say what you checked.
- If nothing was run beyond CI, say so in one line, or post nothing.
- A local test run is worth reporting only if CI cannot repeat it. Then
  say whether the `cdo`-marked tests ran or were skipped.
- Paste output only when the reader needs to see it, and then do not
  restate it in prose.
- Failures unrelated to the branch go under their own heading at the end.

## Calibration

No separate Testing comment has been posted here yet; Heiko's testing
note on #3 was one sentence inside a reply. [Polaris] measured its
Testing comments at 21 to 43 words, and a recent agent-written one there
at 606.

[polaris]: https://github.com/E3SM-Project/polaris

## Enough

What CI cannot do, in one sentence (#3):

> The code has passed real data tests on my machine with various symlink
> setups.

A run on the real archive. Constructed, since none has been posted:

> Ran `ismip7-run-all --domain GrIS --target-res 4000` on the NIRD
> archive: 42 of 44 experiments passed. The two failures are the
> unknown_grid experiments the inventory already lists.

## Too much

"`pytest`: 269 passed" repeats the green check under the pull request.

An agent-written comment in polaris put the table in, then said the same
thing again in prose:

> Every task now runs to completion. The five diffs are all of the form
> `File ... does not exist`: `main` crashed before writing those outputs,
> so there is nothing to compare against. Every comparison that had a file
> on both sides passed. A clean like-for-like comparison for those five
> tasks needs a fresh baseline once this lands.
