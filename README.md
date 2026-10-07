# ismip7-interpolation

Regrids ISMIP7 ice sheet model output, for Greenland (GrIS) and Antarctica
(AIS), onto the standard ISMIP7 grids so that models on different native grids
can be compared. [CDO](https://mpimet.mpg.de/cdo) does the remapping; this
package decides what to remap, how, and where to put it.

**Documentation: <https://ismip.github.io/ismip7-interpolation/>**

## Install

```bash
git clone https://github.com/ismip/ismip7-interpolation.git
cd ismip7-interpolation
conda env create -f ismip7_interp_env.yml
conda activate ismip7-interp
python -m pip install --no-deps --no-build-isolation .
```

The conda environment brings CDO with it; a plain `pip install` of the
package would not, because CDO is a compiled program and is not on PyPI. Keep
the two pip flags: they stop pip from replacing the conda packages with PyPI
wheels. To update, `git pull` and run the `pip install` again.

## Use

The tools read an ISMIP7 archive, laid out as a submission is. The archive
root is the ice sheet directory, the one holding a folder per group:

```
ISMIP7_submissions/GrIS/       <-- --experiments-root
├── NORCE/                     <-- group
│   └── CISM3/                 <-- model
│       └── CORE/              <-- experiment set
│           ├── C001/          <-- experiment
│           │   ├── lithk_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_historical_C001_1850-2014.nc
│           │   └── ...
│           └── C007/
└── AWI/
    └── PISM/
        └── CORE/
            └── C007/
```

```bash
# See what is there before regridding any of it. Reads headers only.
ismip7-inventory --domain GrIS --target-res 4000 \
    --experiments-root ISMIP7_submissions/GrIS --output inventory

# Regrid every experiment in the archive
ismip7-run-all --domain GrIS --target-res 4000 \
    --experiments-root ISMIP7_submissions/GrIS --output-root output

# Regrid one experiment
ismip7-process-experiment --domain GrIS --target-res 4000 \
    --experiments-root ISMIP7_submissions/GrIS \
    ISMIP7_submissions/GrIS/NORCE/CISM3/CORE/C007 output

# Regrid one file
ismip7-interpolate --domain GrIS --target-res 4000 IN.nc OUT.nc
```

Output mirrors the archive under one directory named for the ice sheet and
resolution. Filenames do not change:

```
output/GrIS_04000m/
├── NORCE/CISM3/CORE/C001/lithk_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_historical_C001_1850-2014.nc
├── NORCE/CISM3/CORE/C007/...
├── AWI/PISM/CORE/C007/...
└── logs/
```

Each command is also `python -m ismip7_interp <command>`. Run any of them
with `--help`.

## What it does

- Picks a remapping per variable: conservative by default, bilinear for
  velocity components, and none for time series with no spatial grid.
- Computes remap weights once per grid pair and reuses them across the
  archive.
- Symlinks rather than copies a file that needs no regridding.
- Stops on a grid it does not recognize rather than guessing.
- Logs a failing experiment and moves on. The run fails only if fewer than
  `--min-pass-pct` percent of experiments succeed.

## Where the grids come from

The ISMIP7 grid definitions and the data request are read from the
[ISM_SimulationChecker](https://github.com/ismip/ISM_SimulationChecker)
package, isschecker, so the grids this tool regrids onto cannot drift from the
ones the checker validates against. Which variables get which remapping is
this package's own configuration, in ismip7_interp/data/config. See
[Where the grids and the data request come from](https://ismip.github.io/ismip7-interpolation/user/data-sources.html).

## Developing

Install as above but with `-e` for an editable install, then run the tests:

```bash
python -m pip install --no-deps --no-build-isolation -e .
pytest -v tests
```

See the [developer guide](https://ismip.github.io/ismip7-interpolation/dev/index.html).

## License

MIT, see [LICENSE](LICENSE).
