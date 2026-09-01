# Where the grids and the data request come from

Two of the things this package needs are not its own, and are not kept here:

**The ISMIP7 grid definitions** — the CDO grid description files for the five
AIS and six GrIS target grids.

**The ISMIP7 data request** — which variables exist, which are mandatory, and
which have a spatial grid at all.

Both are maintained in
[ISM_SimulationChecker](https://github.com/ismip/ISM_SimulationChecker) and
read at runtime out of the installed `isschecker` package, which is why it is a
dependency. Nothing is copied into this repository.

## Why not just keep a copy

Because a copy drifts, and both of these already had.

Before this package was ported to Python it carried its own copies of all
eleven grid files and of the variable request. The variable request had gone
stale without anyone noticing: every data row still matched, but the checker's
copy had gained two columns that this one had never heard of.

The grids are the more dangerous of the two. If ISMIP revises a target grid —
an extent, an origin, a size — a stale copy here would mean the compliance
checker validating submissions against the new grid while this tool went on
regridding onto the old one, producing files that were wrong in a way neither
tool would report. Reading both from one place removes that possibility rather
than guarding against it.

## What is still this package's own

The regridding policy, in `ismip7_interp/data/config/`:

- `bilinear_variables.txt` — variables remapped with `remapbil`
- `nearest_variables.txt` — variables remapped with `remapnn`
- `mask_missing_variables.txt` — variables whose missing-value mask must be
  preserved
- `experiment_sets.txt` — which experiment sets and number ranges are open

None of that is part of the data request, and none of it belongs to the
checker: it is about how to remap, not about what a valid submission is. See
{doc}`methods`.

## The scalar-variable list, which no longer exists

A variable with no `x` among its dimensions has no grid to remap. That used to
be a hand-maintained list of ten names; it is now read from the data request's
`Dim` column, where those same ten variables are the ones marked `t`. One
place to be right, instead of two places to agree.

## If the data request changes shape

The package reads three columns: `Variable Name`, `Dim` and
`Mandatory (yes/no)`. If a future data request renames one, the commands fail
with a message saying which column is missing and that this package needs
updating — rather than quietly finding no mandatory variables and reporting a
complete archive.
