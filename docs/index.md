---
hide-toc: true
---

# ISMIP7 Interpolation

`ismip7-interpolation` regrids ISMIP7 ice sheet model output — Greenland
(GrIS) and Antarctica (AIS) — onto the standard ISMIP7 target grids, so that
submissions from models on different native grids can be compared with one
another. [CDO](https://mpimet.mpg.de/cdo) does the remapping; this package
decides what to remap, how, and where to put it.

```bash
conda create -n ismip7-interp -c conda-forge ismip7-interpolation
conda activate ismip7-interp
ismip7-run-all --domain GrIS --target-res 4000 --output-root ./output
```

::: {card} Getting started
:link: getting-started
:link-type: doc

Install the tools, look at an archive, and regrid your first experiment.
:::

::: {card} User guide
:link: user/index
:link-type: doc

The four commands, how a remapping is chosen for each variable, how the
weight cache works, and what the output tree looks like.
:::

::: {card} Developer guide
:link: dev/index
:link-type: doc

Work on the package: install from source, run the test suite, build these
docs, and cut a release.
:::

## What it does

Given an archive of ISMIP7 submissions, the tools:

- **choose a remapping per variable** — conservative by default, bilinear for
  vector velocity components, nearest-neighbour where configured, and none at
  all for the domain-integrated time series that have no spatial grid;
- **cache remap weights** per grid pair and method, so that the expensive part
  of conservative remapping is done once for a whole archive rather than once
  per file;
- **leave alone what does not need changing** — a file already at the target
  resolution, or one with no grid, is symlinked rather than copied;
- **report rather than guess** — a source grid that matches no ISMIP7 grid is
  an error, never an assumption.

There is also a read-only {doc}`inventory <user/inventory>` that says what an
archive holds, how big it would be after regridding, and which mandatory
variables are missing — without reading a byte of data.

## Where things come from

The ISMIP7 grid definitions and the data request are not kept here. They are
maintained in
[ISM_SimulationChecker](https://github.com/ismip/ISM_SimulationChecker) and
read out of the `isschecker` package at runtime, so that the grids this tool
regrids *onto* can never drift from the grids the compliance checker validates
*against*. See {doc}`user/data-sources`.

## Where things live

Developed at
[ismip/ismip7-interpolation](https://github.com/ismip/ismip7-interpolation)
and released through
[conda-forge](https://anaconda.org/conda-forge/ismip7-interpolation). Problems
and questions belong in
[the issue tracker](https://github.com/ismip/ismip7-interpolation/issues).

```{toctree}
:hidden:

getting-started
user/index
dev/index
```
