---
name: pr-descriptions
description: Write or update a pull request description. Use when opening a pull request or editing its body.
---

# Pull request descriptions

The reader is deciding whether to review.

- What changed and why, in a few sentences. Not how.
- Anything needing a reviewer decision goes in its own short list near the
  top, never mid-paragraph.
- A list of changed behaviors is fine. A trace of the mechanism is not.
- No commit list. No testing; that goes in a separate `Testing` comment.
- Link the issue that gives context, with a closing keyword if the pull
  request fixes it.
- Several fixes usually means several pull requests.

## Calibration

The two descriptions written by hand here (#3, #4) are 9 and 49 words.
The two agent-written ones are 195 (#2) and 1810 (#1). That is too few to
measure a tail, so take the rule of thumb from [polaris], a larger
repository with the same maintainer: 27 words at the median, 45 to 62 at
the seventy-fifth percentile, 103 to 110 at the ninetieth, 354 at the
longest.

[polaris]: https://github.com/E3SM-Project/polaris

## Enough

A change in behavior, said in terms of what the user can now do (#3):

> With the fix, you can now specify "--experiments-root ../Models", where
> you had to e.g. specify "--experiments-root ../Models/GrIS/NORCE"
> before. This is the case for both ismip7-inventory and ismip7-run-all.
> Allows for processing whole submission trees at once. This behaviour is
> similar to how the directory root is specified in the checker.

A fix, in one line (#4):

> We saw MacOS failures after the 0.1.0 version tag.

A restructuring, with the changes as a list (ismip/ISM_SimulationChecker#9):

> Convert the flat compliance_checker.py module into a proper package so
> `pip install .` works and the checker runs from any directory.
>
> - Move compliance_checker.py to compliance_checker/__init__.py and add
>   __main__.py (enables `python -m compliance_checker`).
> - Move the runtime CSVs into compliance_checker/data/ as the single
>   source of truth; load them via importlib.resources instead of paths
>   relative to the working directory.
> - Add pyproject.toml declaring the package, data files, dependencies,
>   and the `ismip7-compliance-checker` console script.

## Too much

The description of #1 ran 1810 words, in seven sections, with a "Tests"
section the rules above put in a separate comment. Its "Why" section
opened by tracing what the old scripts could not do:

> `scripts/lib/common.sh` derived every path from the repository root, so
> nothing ran outside a checkout; it ran `conda activate nc` at source
> time when `cdo` was missing, which is one server's environment layout
> baked into a library; and because that activation happened on
> `source`, every unit test had to stub it out before it could load the
> file at all.

Someone deciding whether to review does not need the old scripts traced.
"The scripts only ran from a checkout; this makes them an installable
package" would do, and the rest belongs in the commit messages. The eight
bugs it fixed on the way, each a paragraph, were several pull requests'
worth.
