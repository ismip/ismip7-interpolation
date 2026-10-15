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
    [--weights-dir DIR] \
    EXPERIMENT_DIR OUTPUT_ROOT [--variables VAR1 VAR2 ...]
```

Every .nc file directly inside the experiment directory is regridded, never
anything below it. A file that fails is logged and the rest continue; the
command exits non-zero if any failed.

`--variables` takes one or more variable names and must come after
EXPERIMENT_DIR and OUTPUT_ROOT, which it would otherwise read as variable
names.

Without `--experiments-root`, the last four components of the experiment's
path, group/model/set/experiment, are mirrored into the output.

## A whole archive

```bash
ismip7-run-all --domain GrIS --target-res 4000 \
    [--experiments-root ROOT] [--output-root DIR] \
    [--on-unchanged symlink|copy|skip] [--variables VAR1 VAR2 ...] \
    [--weights-dir DIR] [--groups G1 G2 ...] [--models M1 M2 ...] \
    [--sets SET1 SET2 ...] [--experiments EXP1 EXP2 ...] [--min-pass-pct PCT]
```

A failing experiment is logged and skipped. The run as a whole fails only if
fewer than `--min-pass-pct` percent of experiments succeed, 60 by default.

### Selecting a subset

Without a filter, every experiment in the archive is regridded. The four
subset options each take one or more names and narrow the run to experiments
whose group/model/set/experiment path matches:

```bash
ismip7-run-all --domain AIS --target-res 16000 \
    --experiments-root ../Models/AIS --output-root ../Regridded \
    --groups NORCE --models CISM --sets CORE --experiments C011
```

The filters narrow jointly. The output tree keeps the full
group/model/set/experiment paths, so a filtered run looks exactly like an
unfiltered one of a smaller archive, and the run log records the filters
used. A name that matches no experiment is an error naming it, so a typo
cannot silently leave part of the archive unprocessed; a selection whose
filters match nothing jointly fails the run as "the subset selection matched
none of the N experiment(s) found".

### Which directories count as experiments

Real archives hold abandoned copies and stray trees beside the real
experiments. A directory is processed only when all of these hold:

| Rule | Processed | Skipped |
|---|---|---|
| the experiment set is named exactly as configured | CORE/C001 | old_CORE/C001, CORE_old/C001, CESM2-WACCM_CORE/C001 |
| no directory above it is named old_CORE or CORE_old | CORE/C001 | old_CORE/CORE/C001 |
| its name is the set's prefix and a three-digit number in range | C001 to C011 for CORE | C012 for CORE, P001 for CORE, C1, core001 |
| it holds at least one .nc file directly inside it | CORE/C001/lithk_….nc | CORE/C001/Users/… |

The open experiment sets and their number ranges are in
ismip7_interp/data/config/experiment_sets.txt: CORE (C001-C011),
ESM (E001-E999) and PPE (P001-P999).

## Options

| Option | Meaning | Default |
|---|---|---|
| `--domain` | the ice sheet, GrIS or AIS; required | |
| `--target-res` | the ISMIP7 grid to regrid onto, as a resolution in meters; required | |
| `--experiments-root` | the ice sheet directory of the archive | the NIRD archive for the domain |
| `--output-root` | where the output tree goes; run-all only | output |
| `--variables` | only these variables, by the name that starts each filename, e.g. lithk acabf | every variable |
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

Each name is its own word, split by the shell as usual. Quoting several
names into one word -- `--variables "lithk acabf"` -- is one variable name
that matches no file, and so selects nothing. An experiment with none of the
requested variables is logged and skipped, not counted as a failure, since
some variables are optional.

Every log records the version, so a regridded archive says what produced it.
