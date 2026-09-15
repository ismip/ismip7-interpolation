# Output, logs and the weight cache

## The output tree

Regridding the archive in {doc}`running` to 4 km gives:

```
output/                        <-- --output-root
└── GrIS_04000m/               <-- ice sheet and resolution
    ├── NORCE/
    │   └── CISM3/
    │       └── CORE/
    │           ├── C001/
    │           │   ├── lithk_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_historical_C001_1850-2014.nc
    │           │   └── ...
    │           └── C007/
    └── logs/
        ├── NORCE_CISM3_CORE_C001_20260911T140212Z.log
        ├── NORCE_CISM3_CORE_C007_20260911T140431Z.log
        └── run_20260911T140200Z.log
```

The directory names and the filenames are those of the archive. The one
added directory, GrIS_04000m, carries the resolution, so that the filenames
still follow the ISMIP7 naming convention.

The path below it is the experiment's path relative to `--experiments-root`.
If the experiments root is your model's folder rather than the ice sheet
directory, the group and model are missing from the output:

```
output/GrIS_04000m/CORE/C001/     <-- --experiments-root ISMIP7_submissions/GrIS/NORCE/CISM3
```

For `ismip7-process-experiment` without `--experiments-root`, or with an
experiment outside it, the last four components of the experiment's path are
used: group/model/set/experiment.

## Files that are not regridded

A file with no spatial grid, or one already at the target resolution, is not
put through CDO. `--on-unchanged` says what goes at its output path:

| `--on-unchanged` | Output |
|---|---|
| symlink (default) | an absolute symlink to the source file |
| copy | a real copy, for an output tree that has to stand on its own when moved or archived |
| skip | nothing |

Rerunning replaces an existing file or symlink at the output path. A
directory at that path is refused rather than removed.

## Logs

The logs directory, beside the group directories, holds one timestamped log
per experiment processed and one per `ismip7-run-all` run:

```
logs/
├── NORCE_CISM3_CORE_C001_20260911T140212Z.log   settings, version, OK/FAIL per file
├── NORCE_CISM3_CORE_C007_20260911T140431Z.log
└── run_20260911T140200Z.log                      result per experiment, pass rate
```

An experiment where `--variables` matched nothing still gets a log saying so.
Every log records the package version.

## The weight cache

Conservative remap weights are expensive to compute and depend only on the
two grids, so one weight file per ice sheet, source resolution, target
resolution and method is generated on first use and reused by every file
after it:

```
~/.cache/ismip7-interpolation/weights/
├── GrIS_16000m_to_04000m_ycon.nc
└── GrIS_16000m_to_04000m_bil.nc
```

Move it with `--weights-dir` or the ISMIP7_INTERP_WEIGHTS_DIR environment
variable. The cache never needs backing up: delete it at any time and the
next run regenerates what it needs. A run interrupted while writing weights
cannot leave a truncated file behind.

Weights can be shared because missing source cells are filled with 0 before
remapping, which makes every file's mask the same. The few variables that
keep their real mask, the velocity components, do not use the cache; see
{doc}`methods`.
