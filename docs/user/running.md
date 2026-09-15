# Running the tools

| Command | Regrids |
|---|---|
| `ismip7-interpolate` | one file |
| `ismip7-process-experiment` | one experiment directory |
| `ismip7-run-all` | every experiment in an archive |
| `ismip7-inventory` | nothing; a read-only report, see {doc}`inventory` |

Each is also `python -m ismip7_interp <command>`, which works from a source
checkout that has not been installed.

## The archive

An **experiment** is one directory of NetCDF files for one run, four levels
below the archive root. A **submission** is every experiment from one group
with one model:

```
ISMIP7_submissions/GrIS/       <-- --experiments-root
└── NORCE/                     <-- group
    └── CISM3/                 <-- model
        └── CORE/              <-- experiment set
            ├── C001/          <-- experiment
            └── C007/
```

The experiments root is the ice sheet directory, the one holding a folder per
group. The output tree mirrors the archive below it, so pointing it at a
group or model folder drops those levels from the output; see {doc}`output`.
On NIRD it defaults to the real archive.

## One file

```bash
ismip7-interpolate --domain GrIS --target-res 4000 \
    [--method ycon|bil|nn|auto] [--on-unchanged symlink|copy|skip] \
    [--weights-dir DIR] IN.nc OUT.nc
```

The variable name at the start of the filename decides the remapping.
`--method` overrides that for a variable with a spatial grid; it cannot make
a time series regriddable. See {doc}`methods`.

## One experiment

```bash
ismip7-process-experiment --domain GrIS --target-res 4000 \
    [--experiments-root ROOT] [--on-unchanged symlink|copy|skip] \
    [--variables VAR1,VAR2,...] [--weights-dir DIR] \
    EXPERIMENT_DIR OUTPUT_ROOT
```

Every .nc file directly inside the experiment directory is regridded, never
anything below it. A file that fails is logged and the rest continue; the
command exits non-zero if any failed.

Without `--experiments-root`, the last four components of the experiment's
path, group/model/set/experiment, are mirrored into the output.

## A whole archive

```bash
ismip7-run-all --domain GrIS --target-res 4000 \
    [--experiments-root ROOT] [--output-root DIR] \
    [--on-unchanged symlink|copy|skip] [--min-pass-pct PCT] \
    [--variables VAR1,VAR2,...] [--weights-dir DIR]
```

A failing experiment is logged and skipped. The run as a whole fails only if
fewer than `--min-pass-pct` percent of experiments succeed, 60 by default.

### Which directories count as experiments

Real archives hold abandoned copies and stray trees beside the real
experiments. A directory is processed only when all of these hold:

| Rule | Processed | Skipped |
|---|---|---|
| the experiment set is named exactly as configured | CORE/C001 | old_CORE/C001, CORE_old/C001, CESM2-WACCM_CORE/C001 |
| no directory above it is named old_CORE or CORE_old | CORE/C001 | old_CORE/CORE/C001 |
| its name is the set's prefix and a three-digit number in range | C001 to C011 | C012, C1, core001 |
| it holds at least one .nc file directly inside it | CORE/C001/lithk_….nc | CORE/C001/Users/… |

CORE is the only experiment set open today. The sets and their number ranges
are in ismip7_interp/data/config/experiment_sets.txt.

## Options

| Option | Meaning | Default |
|---|---|---|
| `--domain` | the ice sheet, GrIS or AIS; required | |
| `--target-res` | the ISMIP7 grid to regrid onto, as a resolution in meters; required | |
| `--experiments-root` | the ice sheet directory of the archive | the NIRD archive for the domain |
| `--output-root` | where the output tree goes; run-all only | output |
| `--variables` | only these variables, by the name that starts each filename, e.g. lithk,acabf | every variable |
| `--on-unchanged` | what to put in the output for a file that needs no regridding: symlink, copy or skip | symlink |
| `--weights-dir` | where the remap weights are kept | ~/.cache/ismip7-interpolation/weights |
| `--min-pass-pct` | fail the run if fewer than this percentage of experiments succeed; run-all only | 60 |
| `--method` | the remapping for one file: ycon, bil, nn or auto; interpolate only | auto |
| `-v`, `--verbose` | report each CDO command as it is run | |
| `--version` | print the version | |

Asking for a resolution ISMIP7 does not have lists the ones it does:

```
no ISMIP7 grid for domain=GrIS resolution=4m (known GrIS resolutions: 1000, 2000, 4000, 5000, 8000, 16000)
```

Spaces in `--variables` are fine: `--variables "lithk, acabf"` means what it
looks like. An experiment with none of the requested variables is logged and
skipped, not counted as a failure, since some variables are optional.

Every log records the version, so a regridded archive says what produced it.
