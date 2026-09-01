# Running the tools

Four commands, from one file up to a whole archive. Each is also reachable as
`python -m ismip7_interp <command>`, which is what to use from a source
checkout that has not been installed.

| Command | Scope |
|---|---|
| `ismip7-interpolate` | one file |
| `ismip7-process-experiment` | one experiment directory |
| `ismip7-run-all` | every experiment under an archive root |
| `ismip7-inventory` | a read-only report — see {doc}`inventory` |

## Terminology

An **experiment** is one archive directory,
`<group>/<model>/<experiment-set>/<experiment>` — for example
`NORCE/CISM/CORE/C007` — holding the NetCDF files for one run. A
**submission** is all the experiments from one group with one model. These
tools work per experiment, flattened across every submission in the archive.

## One file

```bash
ismip7-interpolate --domain GrIS|AIS --target-res METERS \
    [--method ycon|bil|nn|auto] [--on-unchanged symlink|copy|skip] \
    [--weights-dir DIR] IN.nc OUT.nc
```

The variable is read from `IN.nc`'s filename — the first `_`-separated token,
per the ISMIP7 convention — and decides the remapping. `--method` overrides
that for a spatial variable; it cannot make a variable with no spatial grid
regriddable, and does not try. See {doc}`methods`.

## One experiment

```bash
ismip7-process-experiment --domain GrIS|AIS --target-res METERS \
    [--experiments-root ROOT] [--on-unchanged symlink|copy|skip] \
    [--variables VAR1,VAR2,...] [--weights-dir DIR] \
    EXPERIMENT_DIR OUTPUT_ROOT
```

Every `.nc` file directly inside `EXPERIMENT_DIR` is regridded — never
anything below it. A file that fails is logged and the rest continue; the
command exits non-zero if any failed.

`--experiments-root` is what the output path is mirrored *from*; see
{doc}`output`.

## A whole archive

```bash
ismip7-run-all --domain GrIS|AIS --target-res METERS \
    [--experiments-root ROOT] [--output-root DIR] \
    [--on-unchanged symlink|copy|skip] [--min-pass-pct PCT] \
    [--variables VAR1,VAR2,...] [--weights-dir DIR]
```

**A failing experiment is not fatal.** Real archives contain non-standard
files, renamed directories and incomplete runs; stopping at the first one
would mean never getting through an archive. Each failure is logged and
stepped over, and the run as a whole fails only if fewer than
`--min-pass-pct` percent of experiments succeeded — 60 by default.

### Which directories count as experiments

A directory is processed when all of these hold:

- it sits inside an experiment-set directory named *exactly* as configured —
  `CORE` today, never `old_CORE`, `CORE_old` or `CESM2-WACCM_CORE`, which
  appear beside the real ones in the archive as abandoned copies;
- no directory above it, up to the archive root, is a deprecated one — the
  archive contains `.../old_CORE/CORE/C001`, a live-looking `CORE` nested
  inside a dead one;
- its own name is the configured prefix and a three-digit number in range —
  `C001` to `C011`;
- it holds at least one `.nc` file **directly inside it**. This is what
  excludes the archive's stray trees, which match the naming but contain
  nothing but a `Users/...` subdirectory.

## Common options

`--domain GrIS|AIS`
: The ice sheet. Required. A grid from one domain is never matched against the
  other.

`--target-res METERS`
: The ISMIP7 target resolution, in meters. Required. A resolution with no
  ISMIP7 grid is an error that lists the ones that exist.

`--experiments-root ROOT`
: The archive to read. Defaults per `--domain` to the known NIRD archive root,
  so on NIRD it can be left out.

`--variables VAR1,VAR2,...`
: Restrict processing to these variables, matched against the first
  `_`-separated token of each filename. Spaces around names are fine:
  `--variables "lithk, acabf"` means what it looks like. An experiment with
  none of them is logged and skipped — some variables are optional and
  legitimately absent — not treated as a failure.

`--on-unchanged symlink|copy|skip`
: What to do with a file that is not actually regridded. Default `symlink`.
  See {doc}`output`.

`--weights-dir DIR`
: Where to cache remap weights. See {doc}`output`.

`-v`, `--verbose`
: Add CDO's own `-v` output, which reports every weight and timing it
  computes. Useful for one file; a great deal for an archive.

`--version`
: Print the version. Every log records it too, so a regridded archive says
  what produced it.
