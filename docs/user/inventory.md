# The inventory

```bash
ismip7-inventory --domain GrIS|AIS --target-res METERS \
    [--experiments-root ROOT] [--output DIR] [--variables VAR1,VAR2,...]
```

A read-only report on what an archive holds. Nothing is regridded and no data
is read — only file sizes and NetCDF headers — so it is cheap enough to run
over a whole archive and safe to run against a read-only one.

`--output` defaults to `./inventory/<domain>`, per domain, so that scanning
GrIS and then AIS does not overwrite the first scan with the second.

## What it writes

`summary.txt`
: Aggregate counts across the scan. Read this first.

`experiments.csv`
: One row per experiment: file count, mandatory-variable completeness, total
  actual and predicted bytes, and a `regrid_status`.

`files.csv`
: One row per file: variable, whether it is mandatory, what kind of file it
  is, its source resolution, and its actual and predicted size.

## regrid_status

`already_at_target`
: Every spatial file already matches `--target-res`.

`needs_regrid`
: At least one spatial file is at a different, recognised ISMIP7 resolution.

`unknown_grid`
: At least one spatial file is on a grid that matches no ISMIP7 grid for this
  domain. **This is the number to look at.** A source grid is never guessed
  at, so these files will fail rather than be silently mis-regridded.

`no_spatial_data`
: No file could be read as a spatial grid at all — everything unreadable
  and/or scalar.

A file CDO or `netCDF4` cannot open is recorded with kind `unreadable` and the
scan carries on. An inventory that stopped at the first bad file would be
exactly the inventory you could not use to find the bad files.

## Predicted sizes

`predicted_target_bytes` is the actual size scaled by the ratio of target grid
points to source grid points. It ignores header overhead, compression and
per-variable data types, so treat it as a ballpark for planning disk, not a
promise. A file with no spatial grid is placed unchanged, so its predicted size
is its actual size; a file whose grid is unknown gets `NA` and is left out of
the experiment's predicted total.

## Mandatory-variable completeness

`missing_mandatory` lists the variables the ISMIP7 data request marks
mandatory that this experiment does not have, and `n_mandatory_present` counts
those it does.

With `--variables`, this is narrowed to match: only requested variables that
are *also* mandatory are expected. Otherwise a filtered scan would report every
mandatory variable it never looked at as missing, which is true of the scan and
false of the archive.

## Speed

`--variables` skips every non-matching file's header read outright rather than
filtering it out of the report, so a filtered scan is genuinely faster and not
just smaller. On a real 44-experiment GrIS archive a full scan takes a minute
or two; one variable takes seconds.

The scan reads headers with `netCDF4` rather than asking CDO, which is what
makes it cheap: the cost does not scale with file size. It also means the
inventory reads some files CDO cannot — the archive holds a whole submission
whose files trip CDO's "time must be the first dimension" check. That is the
right trade for a report on what is *there*, but it does mean the inventory
cannot promise that a file it read will regrid.
