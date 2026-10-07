# Getting started

## Install

```bash
git clone https://github.com/ismip/ismip7-interpolation.git
cd ismip7-interpolation
conda env create -f ismip7_interp_env.yml
conda activate ismip7-interp
python -m pip install --no-deps --no-build-isolation .
ismip7-interpolate --version
```

The conda environment brings CDO with it, which does every remapping. See
{doc}`user/installation` for why the pip flags matter, and
{doc}`dev/source-install` if you mean to work on the package.

## Lay out your files

The tools read an ISMIP7 archive laid out as a submission is. Suppose the
NORCE group's CISM3 model has a Greenland historical run C001 and a
projection C007:

```
ISMIP7_submissions/GrIS/       <-- this is --experiments-root
├── NORCE/                     <-- group
│   └── CISM3/                 <-- model
│       └── CORE/              <-- experiment set
│           ├── C001/          <-- experiment
│           │   ├── lithk_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_historical_C001_1850-2014.nc
│           │   ├── acabf_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_historical_C001_1850-2014.nc
│           │   └── ...
│           └── C007/
│               ├── lithk_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_ssp585_C007_2015-2300.nc
│               └── ...
└── AWI/
    └── PISM/
        └── CORE/
            └── C007/
```

Two things to notice:

- **The experiments root is the ice sheet directory**, ISMIP7_submissions/GrIS
  here: the one holding a folder per group. The output tree mirrors the
  archive below it. If you point it at your own model's folder,
  ISMIP7_submissions/GrIS/NORCE/CISM3, the tools still find the experiments,
  but the output loses the group and model and lands in
  output/GrIS_04000m/CORE/C007 instead of
  output/GrIS_04000m/NORCE/CISM3/CORE/C007.
- **The variable is read from the filename**, the part before the first
  underscore, and decides how the file is remapped. A file named some other
  way gets the default, conservative remapping.

On NIRD, `--experiments-root` defaults to the real archive and can be left
out.

## Look before you regrid

Regridding a whole archive takes time and disk. The inventory takes neither:
it reads file sizes and NetCDF headers, never data.

```bash
ismip7-inventory --domain GrIS --target-res 4000 \
    --experiments-root ISMIP7_submissions/GrIS --output inventory
```

This writes files.csv, experiments.csv and summary.txt. Read the summary
first:

```
domain:             GrIS
target_res_m:       4000
experiments_total:  44
already_at_target:  6
needs_regrid:       35
unknown_grid:       2
no_spatial_data:    1
```

unknown_grid is the number to look at. Those experiments are on a grid that is
not one of the ISMIP7 grids, and they will fail rather than be guessed at.
experiments.csv says which they are. See {doc}`user/inventory`.

## Regrid the archive

```bash
ismip7-run-all --domain GrIS --target-res 4000 \
    --experiments-root ISMIP7_submissions/GrIS --output-root output
```

`--target-res` is in meters. Asking for a resolution ISMIP7 does not have
lists the ones it does:

```
no ISMIP7 grid for domain=GrIS resolution=4m (known GrIS resolutions: 1000, 2000, 4000, 5000, 8000, 16000)
```

The first file on a given pair of grids also generates the remap weights,
which takes a little while. Every file after it reuses them.

A failing experiment is logged and skipped. The run as a whole fails only if
fewer than `--min-pass-pct` percent (60 by default) succeed. See
{doc}`user/running`.

## Regrid one experiment, or one file

```bash
ismip7-process-experiment --domain GrIS --target-res 4000 \
    --experiments-root ISMIP7_submissions/GrIS \
    ISMIP7_submissions/GrIS/NORCE/CISM3/CORE/C007 output
```

```bash
ismip7-interpolate --domain GrIS --target-res 4000 \
    lithk_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_ssp585_C007_2015-2300.nc \
    lithk_regridded.nc
```

## What comes out

```
output/GrIS_04000m/
├── NORCE/
│   └── CISM3/
│       └── CORE/
│           ├── C001/
│           │   ├── lithk_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_historical_C001_1850-2014.nc
│           │   └── ...
│           └── C007/
├── AWI/
│   └── PISM/
│       └── CORE/
│           └── C007/
└── logs/
    ├── NORCE_CISM3_CORE_C001_20260911T140212Z.log
    ├── ...
    └── run_20260911T140200Z.log
```

The tree mirrors the archive, with the same directory and file names. The
resolution is in the one top-level directory, not in the filenames. A file
that needs no regridding, because it is already at the target resolution or
has no spatial grid, is symlinked to the original. See {doc}`user/output`.

## Where to go next

- {doc}`user/running` lists every option of the four commands.
- {doc}`user/methods` says which remapping each variable gets.
- {doc}`user/output` describes the output tree, the logs and the weight cache.
- {doc}`user/data-sources` says where the grids and the data request come from.
