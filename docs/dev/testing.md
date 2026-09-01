# Running the tests

```bash
conda activate ismip7-interp
pytest -v tests
```

The suite imports `ismip7_interp`, so install the package first (see
{doc}`source-install`); the tests then exercise what is actually installed and
can be run from any directory.

## The two halves

Most of the suite is pure logic — name parsing, grid lookup, archive walking,
the decision about which remapping a variable gets, the reports — and runs
anywhere Python does. Those tests replace CDO with a recorder and assert on
the command it *would* have run, which is how the branching gets tested
exhaustively: every combination of variable, method, resolution and
missing-value state, without generating a single weight file.

The rest are marked `cdo` and do real work against small synthetic files
built by CDO itself:

```bash
pytest -v tests -m cdo        # only the ones that regrid
pytest -v tests -m 'not cdo'  # only the ones that do not
```

They skip themselves when CDO is not installed, so a contributor without it
still gets a useful run. CI checks that CDO *is* present before running the
suite, precisely so that a silent skip there cannot mean the remapping went
untested.

`tests/test_end_to_end.py` is all of the pieces together: a two-experiment
archive is inventoried, regridded, and the result checked against the ISMIP7
target grid.

## Writing a test

`tests/conftest.py` holds the shared fixtures:

`fixture_files`
: small synthetic ISMIP7 files, built once per session — a state variable, a
  flux, a velocity component with no missing values and one with a real mask,
  and a scalar time series with no grid at all.

`fake_cdo`
: replaces CDO with a recorder and hands back the list of commands it was
  given. Use this rather than a real regrid whenever the test is about *what
  was decided*.

`write_gridded`
: writes a tiny NetCDF file with given `x` and `y` dimensions, using
  `netCDF4` rather than CDO — which is why the whole inventory can be tested
  without CDO installed.

`make_archive`
: builds a fake archive tree from a mapping of paths to filenames. The files
  are empty, because only names and structure matter to the archive walker.

`weights_dir`
: a throwaway weight cache, so that a test never writes into the developer's
  own.

If you retain the temporary files to look at them:

```bash
pytest -v tests --basetemp=/tmp/pytest_tmp
```

## What CI runs

`.github/workflows/pytest.yml` builds the environment two ways — the ranges in
`ismip7_interp_env.yml` solved fresh, and every floor in it pinned exactly by
`ci/ismip7_interp_env_floor.yml` — on both Linux and macOS, installs the
package with the same pip flags the docs give developers, checks every entry
point answers, and runs the whole suite from outside the checkout so that a
data file or entry point missing from the wheel fails there rather than
passing against the source tree.
