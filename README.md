# ismip7-interpolation

Regrids ISMIP7 ice sheet model output (Greenland/GrIS and
Antarctica/AIS) onto the standard ISMIP7 target grids using CDO.
Picks conservative, bilinear, or nearest-neighbor remapping per
variable automatically, reuses a cached set of remap weights per grid
pair instead of recomputing them for every file, and symlinks (by
default) files already at the target resolution instead of
regridding them. 

**Terminology**: an **experiment** is one archive directory —
`<group>/<model>/<experiment-set>/<experiment>`, e.g.
`NORCE/CISM/CORE/C007` — holding the `.nc` files for one run. A
**submission** is all experiments from one group with one specific
model (e.g. everything under `NORCE/CISM`, which may include multiple
experiment sets/numbers). The tooling here operates per-experiment,
flattened across the whole archive.

## Usage

All scripts live in `scripts/` and share config in `config/` and grid
definitions in `gdfs/`. They're self-contained bash + CDO
Run them from the repo root:

```bash
ssh nird
cd /path/to/ismip7-interpolation
scripts/run_all_experiments.sh --domain GrIS --target-res 4000
```

`cdo` is expected on `PATH`; on NIRD, `scripts/lib/common.sh` runs
`conda activate nc` automatically if `cdo` isn't already available.
On another server, either activate an environment with `cdo` before
running the scripts, or adjust `ensure_cdo()` in
`scripts/lib/common.sh` for that server's setup.

```bash
# Regrid a single file
scripts/interpolate_variable.sh --domain GrIS|AIS --target-res METERS \
    [--method ycon|bil|nn|auto] [--on-unchanged symlink|copy|skip] IN.nc OUT.nc

# Regrid every file in one experiment directory
scripts/process_experiment.sh --domain GrIS|AIS --target-res METERS \
    [--on-unchanged symlink|copy|skip] [--variables VAR1,VAR2,...] \
    EXPERIMENT_DIR OUTPUT_ROOT

# Regrid every experiment found under an archive root
scripts/run_all_experiments.sh --domain GrIS|AIS --target-res METERS \
    [--experiments-root ROOT] [--output-root DIR] \
    [--on-unchanged symlink|copy|skip] [--min-pass-pct PCT] \
    [--variables VAR1,VAR2,...]

# Read-only inventory report (sizes, predicted post-regrid sizes,
# mandatory-variable completeness, regrid-need summary) -- never
# regrids anything; much faster than the regrid scripts (ncdump-based
# grid detection, not cdo -- see Architecture in CLAUDE.md)
scripts/inventory_archive.sh --domain GrIS|AIS --target-res METERS \
    [--experiments-root ROOT] [--output DIR] [--variables VAR1,VAR2,...]
```

**Processing only specific variables**: `--variables lithk,acabf` (comma-separated,
matched against the first `_`-separated token of each filename)
restricts `process_experiment.sh`/`run_all_experiments.sh`/
`inventory_archive.sh` to just those variables, across every
experiment. An experiment missing a requested variable isn't an
error — it's logged and skipped. On `inventory_archive.sh` this also
skips the (relatively expensive) grid-detection step for every
non-matching file, so a filtered scan is noticeably faster than a full
one, not just a smaller report.

**Archive path**: `--experiments-root` points at the archive to scan.
It defaults per `--domain` to the known archive root (both GrIS and
AIS are confirmed); pass `--experiments-root` explicitly to point at
anything else instead (a test copy, a different mount). To change a
default itself, edit it in `scripts/run_all_experiments.sh` and
`scripts/inventory_archive.sh`.

**Files that aren't actually regridded** (a scalar variable with no
spatial grid, or a file already at the target resolution) are placed
at the output path per `--on-unchanged`, default `symlink` — an
absolute symlink back to the source file, avoiding a full copy of
data that isn't changing. Pass `--on-unchanged copy` for a real copy,
or `--on-unchanged skip` to write nothing for that file at all.

**Remap weights are cached** under `weights/` (gitignored, empty on
checkout, populated automatically the first time each
domain/source-resolution/target-resolution/method combination is
regridded). This is a large speedup on a real archive — regridding a
file no longer recomputes conservative-remap weights from scratch
every time — and requires no action from you; missing weight files
are generated on demand from the grid definitions alone, never from
archive data. Before caching, missing source cells are filled with
`cdo setmisstoc,0` so the weights don't depend on which cells happen
to be missing in a given file — safe for most variables (e.g. ice
thickness, where "no ice" is legitimately 0), but wrong for a few
(e.g. ice velocity, where 0 isn't a meaningful fill value outside the
ice sheet). `config/mask_missing_variables.txt` lists the variables
that keep their real missing-value pattern instead; add a variable
there if regridding it needs the same treatment.

**Partial failures are expected**, not fatal: real experiments vary
in quality, and `run_all_experiments.sh` logs a failed experiment and
moves on rather than aborting the whole run. It only exits non-zero
if the overall pass rate drops below `--min-pass-pct` (default 60).

Output is only ever written under the writable NIRD working directory
(`/nird/datapeak/NS5011K/users/heig/RemoteTesting/ismip7-interpolation`)
— the archive itself is read-only.

## Expected archive structure

```
<root>/<group>/<model>/<experiment-set>/<experiment>/*.nc
```

e.g. `NORCE/CISM/CORE/C007/acabf_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_ssp585_C007_2015-2300.nc`.

- `<experiment-set>` and the allowed `<experiment>` number range are
  configured in `config/experiment_sets.txt` (currently only `CORE`,
  numbers `C001`-`C011`). A directory must match this *exactly* to be
  picked up — variants like `old_CORE`, `CORE_old`, or an experiment
  number out of range are skipped, along with any directory that has
  no `.nc` files directly inside it.
- Filenames follow the ISMIP7 convention:
  `{var}_{region}_{project}_{submission}_{modelid}_{ESM}_{forcingid}_{experiment}_{configid}_{startyear}-{endyear}.nc`
  (no resolution token).

## Output structure

```
OUTPUT_ROOT/<DOMAIN>_<res>m/<group>/<model>/<experiment-set>/<experiment>/*.nc
OUTPUT_ROOT/<DOMAIN>_<res>m/logs/
```

e.g. `OUTPUT_ROOT/GrIS_04000m/NORCE/CISM/CORE/C007/acabf_..._2015-2300.nc`.
The group/model/experiment-set/experiment directory names and the
filenames are identical to the source archive — only the top-level
`<DOMAIN>_<res>m` directory is added, carrying the resolution instead
of the filename.

`logs/`, alongside the group directories, holds a timestamped log per
experiment processed (from `process_experiment.sh`, whether run
directly or via `run_all_experiments.sh`) plus one consolidated
timestamped run log per `run_all_experiments.sh` invocation. Each log
records what was processed, the `--on-unchanged`/target-resolution
settings used, and the scripts' git commit at run time (once this
repo is on git — until then it records that explicitly rather than
guessing).

## Inventory output

`inventory_archive.sh` writes `DIR/files.csv` (one row per file),
`DIR/experiments.csv` (one row per experiment, including a
`regrid_status` of `already_at_target` / `needs_regrid` /
`unknown_grid` / `no_spatial_data`), and `DIR/summary.txt` (aggregate
counts across the scan) — `DIR` defaults to
`<repo>/output/inventory_<domain>` (e.g. `output/inventory_GrIS`), so
scanning both domains without `--output` never overwrites either
scan. On the real GrIS archive (44 experiments) a full scan takes
~1-2 minutes; restricting to one variable with `--variables` cuts
that to a few seconds.
