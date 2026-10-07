# The inventory

```bash
ismip7-inventory --domain GrIS --target-res 4000 \
    [--experiments-root ROOT] [--output DIR] [--variables VAR1,VAR2,...]
```

A read-only report on what an archive holds. Nothing is regridded and no
data is read, only file sizes and NetCDF headers, so it is cheap to run over
a whole archive and safe against a read-only one.

## What it writes

```
inventory/GrIS/           <-- --output; the default is per ice sheet
├── summary.txt           counts across the archive; read this first
├── experiments.csv       one row per experiment
└── files.csv             one row per file
```

summary.txt:

```
domain:             GrIS
target_res_m:       4000
experiments_root:   /nird/datalake/NS5011K/ISMIP/ISMIP7/GrIS/ISMIP7_output/ISMIP7_submissions/GrIS
variables:          (all)
version:            0.1.0
scanned_utc:        2026-09-11T14:02:00Z
experiments_total:  44
already_at_target:  6
needs_regrid:       35
unknown_grid:       2
no_spatial_data:    1
```

experiments.csv has, per experiment, the file count, which mandatory
variables are missing, the actual and predicted total bytes, and a
regrid_status. files.csv has, per file, the variable, whether it is
mandatory, what kind of file it is, its source resolution, and its actual and
predicted size.

## regrid_status

| Status | Meaning |
|---|---|
| already_at_target | every spatial file is already at `--target-res` |
| needs_regrid | at least one spatial file is at another ISMIP7 resolution |
| unknown_grid | at least one spatial file is on a grid that is not an ISMIP7 grid for this ice sheet |
| no_spatial_data | no file could be read as a spatial grid |

**unknown_grid is the number to look at.** A source grid is never guessed,
so those files will fail when regridded. files.csv says which they are.

A file that cannot be opened is recorded with kind unreadable and the scan
carries on.

## Predicted sizes

predicted_target_bytes is the actual size scaled by the ratio of target to
source grid points. It ignores header overhead, compression and data types,
so treat it as a ballpark for planning disk. A file with no spatial grid
keeps its actual size; a file on an unknown grid gets NA and is left out of
the experiment's total.

## Mandatory variables

missing_mandatory lists the variables the ISMIP7 data request marks mandatory
that the experiment does not have; n_mandatory_present counts those it does.
With `--variables`, only requested variables that are also mandatory count.

## Speed

`--variables` skips the header read for every other file, so a filtered scan
is faster and not just smaller. On a 44-experiment Greenland archive a full
scan takes a minute or two; one variable takes seconds.

Headers are read with netCDF4 rather than CDO, so the inventory can read some
files CDO cannot. An experiment the inventory reads is not guaranteed to
regrid.
