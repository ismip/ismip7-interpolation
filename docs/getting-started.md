# Getting started

## Install

```bash
conda create -n ismip7-interp -c conda-forge ismip7-interpolation
conda activate ismip7-interp
```

That brings CDO with it, which is what actually performs every remapping. If
you would rather work on the package than use it, see
{doc}`dev/source-install`.

Check that it worked:

```bash
ismip7-interpolate --version
```

## Look before you regrid

Regridding a whole archive takes time and disk. The inventory takes neither:
it reads file sizes and NetCDF headers, never data, and tells you what you are
about to be dealing with.

```bash
ismip7-inventory --domain GrIS --target-res 4000 \
    --experiments-root /path/to/archive --output ./inventory
```

That writes `files.csv`, `experiments.csv` and `summary.txt`. The summary is
the one to read first:

```
domain:             GrIS
target_res_m:       4000
experiments_total:  44
already_at_target:  6
needs_regrid:       35
unknown_grid:       2
no_spatial_data:    1
```

`unknown_grid` is the interesting number: those are experiments on a grid that
is not one of the ISMIP7 grids, and they will fail rather than be guessed at.
See {doc}`user/inventory`.

## Regrid one file

```bash
ismip7-interpolate --domain GrIS --target-res 4000 \
    lithk_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_ssp585_C007_2015-2300.nc \
    lithk_regridded.nc
```

The variable name is read from the filename — the first `_`-separated token —
and decides which remapping is used. The first run for a given grid pair also
generates the remap weights, which takes a little while; every run after it
reuses them.

## Regrid an archive

```bash
ismip7-run-all --domain GrIS --target-res 4000 \
    --experiments-root /path/to/archive --output-root ./output
```

Output lands under `./output/GrIS_04000m/`, mirroring the archive's
`group/model/experiment-set/experiment` directories with the filenames
unchanged. A per-experiment log and one run log go in
`./output/GrIS_04000m/logs/`.

Not every experiment in a real archive processes cleanly, and that is expected
rather than fatal: a failing experiment is logged and stepped over. The run as
a whole fails only if fewer than `--min-pass-pct` (default 60) percent
succeeded. See {doc}`user/running`.

## Where to go next

- {doc}`user/running` — the four commands and their options.
- {doc}`user/methods` — which remapping each variable gets, and why.
- {doc}`user/output` — the output tree, the logs, and the weight cache.
- {doc}`user/data-sources` — where the grids and the data request come from.
