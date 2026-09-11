# Where the grids and the data request come from

Two things this package needs are the ISMIP7 project's, not its own:

- **the ISMIP7 grid definitions**, CDO grid description files for the five
  Antarctic and six Greenland target grids;
- **the ISMIP7 data request**, which says which variables exist, which are
  mandatory, and which have a spatial grid.

Both are maintained in
[ISM_SimulationChecker](https://github.com/ismip/ISM_SimulationChecker) and
read from its isschecker package, which is why it is a dependency. Nothing
is copied into this repository, so the grids this tool regrids onto cannot
drift from the ones the compliance checker validates against. An earlier
copy of the data request here had gone stale without anyone noticing.

## What is this package's own

The regridding policy, in ismip7_interp/data/config:

| File | Holds |
|---|---|
| bilinear_variables.txt | variables remapped bilinearly |
| nearest_variables.txt | variables remapped nearest-neighbor |
| mask_missing_variables.txt | variables that keep their real missing-value mask |
| experiment_sets.txt | which experiment sets and number ranges are open |

This is about how to remap, not about what a valid submission is. See
{doc}`methods`.

## If the data request changes shape

The package reads three columns of the data request: Variable Name, Dim and
Mandatory (yes/no). If a future request renames one, the commands stop with
a message naming the missing column, rather than quietly finding no mandatory
variables and reporting a complete archive.
