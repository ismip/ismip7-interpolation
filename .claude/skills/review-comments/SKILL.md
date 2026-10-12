---
name: review-comments
description: Write a review comment, review findings, or a reply to review feedback on a GitHub pull request. Use when reviewing code, reporting what testing someone else's branch turned up, or answering a reviewer's question.
---

# Review comments

The reader is deciding what to change.

- Put each finding as an inline comment on the line it concerns, one point
  each. That is where colleagues put them, and it is why their review
  bodies are short.
- The review body summarizes: what you ran, and the verdict. Two or three
  sentences.
- Use a list in the body only for requests that span files.
- No section on what already works. One line for all of it, if any.
- Say what you could not check, such as the real archive on NIRD.
- A reply answers the question asked. Quote the question only when the
  thread has moved on since it was put.

## Calibration

Review bodies here run from one line ("I didn't formally approve
before!") to about 250 words, and are too few to measure a tail. Take the
rule of thumb from [polaris]: review bodies at 14 words at the median, 55
at the ninetieth percentile and 239 at the longest; inline comments at 22
to 32 words at the median and 170 at the longest.

[polaris]: https://github.com/E3SM-Project/polaris

## Enough

One finding, on the line, with the case that shows it and a fix (#3):

> **The paths are now compared as text.** Dropping `.resolve()` fixes the
> symlink case, but a relative experiment directory and an absolute root
> no longer match. For example, `ismip7-process-experiment
> GrIS/NORCE/CISM/CORE/C001 --experiments-root /abs/GrIS` now falls back
> to the last four path components. On `main` the two paths matched.
>
> I'd suggest applying `os.path.abspath()` to both paths. It makes them
> comparable without following symlinks.

A reply that answers the question, and says only what changed (#3):

> Hi Xylar, I have reworked the branch (and PR) to address (most of) your
> suggestions.
> 1. The changes that removed resolution from the output path have been
>    reverted.
> 2. The potential side effects with allowing symlinks in the path. The
>    code has passed real data tests on my machine with various symlink
>    setups.
> 3. The remaining points are also addressed.

## Too much

The review body on #3 listed its own inline comments again:

> I've left a few comments inline that I'd like to sort out before
> merging: the output path losing the resolution, duplicate experiments
> when symlinks are followed, a regression in `experiment_rel_path` for
> relative vs. absolute paths, and help text that `process-experiment`
> doesn't live up to.

"A few comments inline to sort out before merging" would do; the reader
is about to see each one on its line.

A bot review on ismip/ISM_SimulationChecker#25 spent 455 words on "Pull
request overview", "Changes" and "Reviewed changes", all restating the
pull request, before its two inline findings. One of the two was wrong:

> The comment above `FILL_POLICY_MEANINGS` refers to a "Missing values
> and masks" section in `/user/errors-and-warnings`, but that section
> doesn't exist in this docs tree. This can mislead future maintainers
> when they try to update the generated tables.

The section existed. A finding is checked before it is written, and the
overview is what the pull request description is for.
