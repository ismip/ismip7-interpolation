---
hide-toc: true
---

# ISMIP7 Interpolation

Regrids ISMIP7 ice sheet model output, for Greenland (GrIS) and Antarctica
(AIS), onto the standard ISMIP7 grids so that models on different native grids
can be compared. [CDO](https://mpimet.mpg.de/cdo) does the remapping; this
package decides what to remap, how, and where to put it.

```bash
git clone https://github.com/ismip/ismip7-interpolation.git
cd ismip7-interpolation
conda env create -f ismip7_interp_env.yml
conda activate ismip7-interp
python -m pip install --no-deps --no-build-isolation .
ismip7-run-all --domain GrIS --target-res 4000 \
    --experiments-root ISMIP7_submissions/GrIS --output-root output
```

::: {card} Getting started
:link: getting-started
:link-type: doc

Install the tools, lay out the archive, look at what is in it, and regrid it.
:::

::: {card} User guide
:link: user/index
:link-type: doc

The four commands, how a remapping is chosen for each variable, and what the
output tree looks like.
:::

::: {card} Developer guide
:link: dev/index
:link-type: doc

Install from source, run the tests, build these docs, and cut a release.
:::

## What it does

Given an archive of ISMIP7 submissions, the tools:

- pick a remapping per variable: conservative by default, bilinear for
  velocity components, and none for time series with no spatial grid;
- compute remap weights once per grid pair and reuse them across the archive;
- symlink rather than copy a file that needs no regridding;
- stop on a grid they do not recognize rather than guess.

The {doc}`inventory <user/inventory>` says what an archive holds, how big it
would be after regridding, and which mandatory variables are missing, without
reading any data.

## Where the grids come from

The ISMIP7 grid definitions and the data request are read from the
[ISM_SimulationChecker](https://github.com/ismip/ISM_SimulationChecker)
package, isschecker, so the grids this tool regrids onto cannot drift from
the ones the checker validates against. See {doc}`user/data-sources`.

## Where things live

Developed at
[ismip/ismip7-interpolation](https://github.com/ismip/ismip7-interpolation).
Problems and questions go in
[the issue tracker](https://github.com/ismip/ismip7-interpolation/issues).

```{toctree}
:hidden:

getting-started
user/index
dev/index
```
