# Output, logs and the weight cache

## The output tree

```
OUTPUT_ROOT/<DOMAIN>_<res>m/<group>/<model>/<experiment-set>/<experiment>/*.nc
OUTPUT_ROOT/<DOMAIN>_<res>m/logs/
```

For example
`./output/GrIS_04000m/NORCE/CISM/CORE/C007/acabf_..._2015-2300.nc`.

The directory names and the filenames are exactly those of the source archive.
Only the top-level `<DOMAIN>_<res>m` directory is added, and it is what
carries the resolution — **not** the filenames, which would otherwise have to
be rewritten and would then no longer match the ISMIP7 naming convention.

The mirrored path is the experiment's path relative to `--experiments-root`.
If the experiment is not under that root — or none was given — the last four
components are used instead, which is the
`group/model/experiment-set/experiment` tail of a well-formed archive path.
Four and not three: two groups can hold the same model, set and experiment
number, and dropping the group would write both into one directory.

## Files that are not regridded

A file with no spatial grid, or one already at the target resolution, is not
put through CDO. `--on-unchanged` says what to put at its output path instead:

`symlink` (default)
: An absolute symlink back to the source file. Nothing is copied, which
  matters when the file is large and unchanged, and the link resolves wherever
  the output tree is read from.

`copy`
: A real copy. Use this when the output tree has to stand on its own — being
  moved to another machine, or archived — where a symlink into the source
  archive would dangle.

`skip`
: Nothing is written at all.

Reruns are idempotent: an existing file or symlink at the output path is
replaced. A *directory* at that path is refused rather than removed — that is
an anomaly, not a stale result, and deleting one could throw away a great deal.

## Logs

`logs/`, alongside the group directories, holds:

- one timestamped log per experiment processed, whether run directly or
  through `ismip7-run-all`, recording the settings used, the package version,
  and a per-file `OK`/`FAIL` result;
- one timestamped run log per `ismip7-run-all` invocation, with the
  per-experiment results and the pass rate.

An experiment where `--variables` matched nothing still gets a log saying so.
"This experiment has none of the variables you asked for" is a result worth
having on disk, not an absence to puzzle over later.

Every log records the package version, so a regridded archive says what
produced it.

## The weight cache

Conservative remap weights are expensive to compute and depend only on the
geometry of the two grids — not on the data — once the missing-value mask has
been made uniform (see {doc}`methods`). So one weight file per
(domain, source resolution, target resolution, method) is generated on first
use and reused by every file after it:

```
GrIS_16000m_to_04000m_ycon.nc
GrIS_16000m_to_04000m_bil.nc
```

This is a large speedup across a real archive, and needs nothing from you.
Weights are generated from a synthetic constant field on the source grid, never
from archive data, which keeps the read-only archive out of it entirely.

By default the cache lives in `~/.cache/ismip7-interpolation/weights`
(or under `$XDG_CACHE_HOME`), because the package itself may well be installed
read-only. Override it with `--weights-dir` or the
`ISMIP7_INTERP_WEIGHTS_DIR` environment variable.

The cache is reproducible from the grid definitions alone, so it never needs
backing up and can be deleted at any time — the next run regenerates what it
needs. Weights are written to a temporary file and renamed into place, so a
run interrupted part-way through cannot leave a truncated file for a later run
to trust.
