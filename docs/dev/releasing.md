# Releasing

This page is for maintainers — those with write access to
[the main repository](https://github.com/ismip/ismip7-interpolation). If you
are contributing from a fork, nothing here is yours to do; open the pull
request and a maintainer will fold it into the next release.

Modelers get the tools from conda-forge, and conda-forge builds from a tag.
Anything on `main` that has not been tagged therefore does not exist as far as
they are concerned: a remapping you changed, a variable you moved between
configuration lists, a bug you fixed — all of it sits in this repository being
invisible to everyone running the tools.

**So tag a release whenever a change reaches `main` that a user would notice.**
That is deliberately a low bar: a variable moving into or out of
`bilinear_variables.txt`, `nearest_variables.txt` or
`mask_missing_variables.txt`; a change to `experiment_sets.txt`; a new or
altered command-line option; a change to the output tree or the log format; a
bug fix; or a widened dependency range. Releases are cheap; a user chasing a
discrepancy against a source checkout that turns out to be six months of
untagged changes is not. Refactorings, tests, CI and documentation-only
changes need no release, though there is no harm in folding them into the next
one.

```{important}
A change to which remapping a variable gets changes the *numbers* in every
file regridded afterwards. Say so plainly in the release notes: someone may
have results from the previous version and needs to know they are not
comparable.
```

## Cutting a release

1. Bump `version` in `pyproject.toml` following
   [semantic versioning](https://semver.org/) — patch for a fix, minor for a
   new option or a new configured variable, major for a change that would give
   materially different output for the same input — and merge that to `main`.

2. Draft a new
   [GitHub release](https://github.com/ismip/ismip7-interpolation/releases/new)
   against `main`. In the tag field, type the new version and choose **Create
   new tag on publish**, so that publishing the release creates the tag: one
   action, and the two can never disagree about which commit they point at.
   Write notes saying what changed for users, then publish.

   The tag is the bare version number — `0.1.0`, no `v` prefix — because the
   feedstock builds its source URL from it, and it must match `version` in
   `pyproject.toml` exactly.

3. Wait for the conda-forge bot to open a version-bump PR on
   `ismip7-interpolation-feedstock`, usually within a few hours. Review and
   merge it; the package appears on conda-forge shortly after the build
   finishes. Merging it needs write access to the feedstock, which is separate
   from write access here — see [Maintaining the
   feedstock](#maintaining-the-feedstock) below.

If the release changed the dependency ranges, edit the feedstock PR before
merging so that the `run:` requirements in `recipe/recipe.yaml` match
`pyproject.toml` and `ismip7_interp_env.yml` — the bot updates the version and
hash, not the requirements.

```{warning}
**CDO must be in the feedstock's `run:` requirements, and cannot come from
`pyproject.toml`.** It is not on PyPI, so it is absent from the Python
metadata the bot reads; nothing will add it for you. A recipe that omits it
builds and passes its own import test, and then gives every user a package
that cannot regrid anything. The same is true of `isschecker`, which ships the
grids and the data request. Check both on every release that touches
requirements.
```

## The relationship with isschecker

This package reads the ISMIP7 grid definitions and data request out of
`isschecker` at runtime (see {doc}`../user/data-sources`). Two consequences
for releasing:

- **A data request change is released by `isschecker`, not here.** If a
  variable is added or a mandatory flag changes, users get it by updating
  `isschecker`; this package needs no release at all. That is the point of not
  copying it.
- **A change to which columns we read is a change here.** The package reads
  `Variable Name`, `Dim` and `Mandatory (yes/no)`. If a future data request
  renames one, this package needs a release with the new name, and its
  `isschecker` floor raised to the version that has it.

## Confirming what was published

Optionally, confirm what was published rather than assuming it:

```bash
conda create -n ismip7-interp-test -c conda-forge --override-channels \
    ismip7-interpolation pytest
conda activate ismip7-interp-test
ismip7-interpolate --version    # should print the version you tagged
cdo --version                   # should be there at all -- see the warning above
cd $(mktemp -d) && pytest -v /path/to/ismip7-interpolation/tests
```

Run that from a checkout of the tag, not of `main`: the tests come from the
source tree while the package comes from conda-forge, so with `main` checked
out any change made since the tag shows up as a test failure that says nothing
about the release.

It is optional because of the wait. A merged feedstock PR does not put the
package within reach immediately: the build has to finish, and the result then
takes roughly an hour to propagate across the servers `conda` fetches from.
Until it has, `conda create` either cannot find the new version or reports the
old one, and neither means anything is wrong. So this is not a step to sit and
retry — come back to it later in the day, or skip it. What it does catch is
the recipe describing something other than what you tagged, which for this
package includes the missing-CDO case above, and that is worth a few minutes
after any release that changed requirements.

## Maintaining the feedstock

The conda-forge package is built by its own repository, separate from this one
and with its own list of maintainers — being a maintainer here does not make
you one there. Only feedstock maintainers can merge the bot's version-bump
PRs, so a release stalls if nobody available has that access. It is worth
having more than one of us on the list.

The list lives in the recipe itself, under `extra: recipe-maintainers:` in
`recipe/recipe.yaml`. To be added, open an **issue** on the feedstock with the
title:

```
@conda-forge-admin, please add user @your-github-username
```

A bot then opens a PR adding you, which an existing feedstock maintainer
merges. GitHub will email you an invitation to the feedstock's team in the
conda-forge organization; **you have to accept it**, or the merge has given you
nothing. This is conda-forge's documented mechanism, described under
[Updating the maintainer list](https://conda-forge.org/docs/maintainer/updating_pkgs/#updating-the-maintainer-list);
leave the bot's PR alone rather than editing it or its commit message, since it
is built to skip a package rebuild.

[The conda-forge maintainer documentation](https://conda-forge.org/docs/maintainer/)
covers the rest: what the bots do, how to fix a build, and the
[`@conda-forge-admin` commands](https://conda-forge.org/docs/maintainer/infrastructure/#conda-forge-admin-please-add-user-username)
for re-rendering a feedstock and other routine chores.
