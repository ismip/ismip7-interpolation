# ismip7-interpolation

Regrid ISMIP7 ice sheet model output — Greenland (GrIS) and Antarctica (AIS) —
onto the standard ISMIP7 target grids, so that submissions from models on
different native grids can be compared with one another.
[CDO](https://mpimet.mpg.de/cdo) does the remapping; this package decides what
to remap, how, and where to put it.

**Documentation: <https://ismip.github.io/ismip7-interpolation/>**

## Install

```bash
conda create -n ismip7-interp -c conda-forge ismip7-interpolation
conda activate ismip7-interp
```

That brings CDO with it, which is what actually performs every remapping.
`pip install` gives you the Python code with nothing to run it — CDO is a
compiled program and is not on PyPI.

## Use

```bash
# Look at an archive without touching it: sizes, predicted post-regrid sizes,
# mandatory-variable completeness, and which experiments are on a grid we
# don't recognise. Reads headers only, never data.
ismip7-inventory --domain GrIS --target-res 4000 \
    --experiments-root /path/to/archive --output ./inventory

# Regrid every experiment under an archive root
ismip7-run-all --domain GrIS --target-res 4000 \
    --experiments-root /path/to/archive --output-root ./output

# Regrid one experiment directory
ismip7-process-experiment --domain GrIS --target-res 4000 \
    EXPERIMENT_DIR OUTPUT_ROOT

# Regrid one file
ismip7-interpolate --domain GrIS --target-res 4000 IN.nc OUT.nc
```

Each is also `python -m ismip7_interp <command>`. Run any of them with
`--help`.

## What it does

- **Chooses a remapping per variable** — conservative (`remapycon`) by
  default, bilinear (`remapbil`) for vector velocity components, and none at
  all for the domain-integrated time series that have no spatial grid.
- **Caches remap weights** per grid pair and method, so the expensive part of
  conservative remapping happens once for a whole archive rather than once per
  file.
- **Leaves alone what does not need changing** — a file already at the target
  resolution, or one with no grid, is symlinked rather than copied.
- **Reports rather than guesses** — a source grid matching no ISMIP7 grid is an
  error, never an assumption.
- **Keeps going** — a failing experiment in a real archive is logged and
  stepped over; the run fails only below `--min-pass-pct`.

Output mirrors the archive under one `<DOMAIN>_<res>m` directory, with
filenames unchanged and timestamped logs alongside:

```
OUTPUT_ROOT/GrIS_04000m/<group>/<model>/<experiment-set>/<experiment>/*.nc
OUTPUT_ROOT/GrIS_04000m/logs/
```

## Grids and the data request come from isschecker

The ISMIP7 grid definitions and the data request are maintained in
[ISM_SimulationChecker](https://github.com/ismip/ISM_SimulationChecker) and
read out of the `isschecker` package at runtime rather than copied into this
one. That is deliberate: it means the grids this tool regrids *onto* cannot
drift from the grids the compliance checker validates *against*. See
[Where the grids and the data request come from](https://ismip.github.io/ismip7-interpolation/user/data-sources.html).

What *is* configured here is the regridding policy, in
`ismip7_interp/data/config/` — which variables need bilinear or
nearest-neighbour remapping, whose missing-value mask must be preserved, and
which experiment sets are open.

## Developing

```bash
conda env create -f ismip7_interp_env.yml
conda activate ismip7-interp
python -m pip install --no-deps --no-build-isolation -e .
pytest -v tests
```

See the [developer guide](https://ismip.github.io/ismip7-interpolation/dev/index.html).

## License

MIT — see [LICENSE](LICENSE).
