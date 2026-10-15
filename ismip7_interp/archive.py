"""Finding experiments in an ISMIP7 submission archive.

An **experiment** is one directory, ``<group>/<model>/<experiment-set>/
<experiment>`` -- for example ``NORCE/CISM/CORE/C007`` -- holding the NetCDF
files for one run.  All the experiments from one group with one model together
are a **submission**; everything here works per experiment, flattened across
every submission in the archive.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ismip7_interp.paths import config_dir

LOGGER = logging.getLogger(__name__)

#: Where each domain's archive lives on NIRD, used when ``--experiments-root``
#: is not given.  Both are confirmed; anywhere else needs the option.
DEFAULT_EXPERIMENTS_ROOT = {
    'GrIS': Path('/nird/datalake/NS5011K/ISMIP/ISMIP7/GrIS/ISMIP7_output/'
                 'ISMIP7_submissions/GrIS'),
    'AIS': Path('/nird/datalake/NS5011K/ISMIP/ISMIP7/AIS/ISMIP7_output/'
                'ISMIP7_submissions/AIS'),
}

#: Experiment-set directory names that mark a deprecated or superseded copy.
#: Matched case-insensitively against every component of the path, not just the
#: directory's own name: the archive has ``.../old_CORE/CORE/C001``, a
#: live-looking ``CORE`` nested inside a dead one.
_DEPRECATED_MARKERS = ('old_core', 'core_old')

#: How many path components below the archive root an experiment sits:
#: group/model/experiment-set/experiment.
EXPERIMENT_PATH_DEPTH = 4


@dataclass(frozen=True)
class ExperimentSet:
    """One allowed experiment set and the experiment numbers it may contain."""

    name: str
    prefix: str
    min_number: int
    max_number: int

    def matches(self, directory_name: str) -> bool:
        """Return whether an experiment directory belongs to this set."""
        match = re.fullmatch(rf'{re.escape(self.prefix)}(\d{{3}})',
                             directory_name)
        if match is None:
            return False
        return self.min_number <= int(match.group(1)) <= self.max_number


@lru_cache(maxsize=None)
def experiment_sets() -> tuple[ExperimentSet, ...]:
    """Return the experiment sets configured as open for processing."""
    path = config_dir() / 'experiment_sets.txt'
    sets = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        fields = line.split()
        if len(fields) != 4:
            raise ValueError(
                f'{path}:{number}: expected "set_name prefix min max", got '
                f'{line!r}')
        name, prefix, minimum, maximum = fields
        sets.append(ExperimentSet(name, prefix, int(minimum), int(maximum)))
    return tuple(sets)


def _has_deprecated_ancestor(path: Path, root: Path) -> bool:
    """Return whether a component of ``path`` below ``root`` is deprecated."""
    try:
        parts = path.relative_to(root).parts
    except ValueError:  # pragma: no cover - path is always under root
        parts = path.parts
    return any(marker in part.lower()
               for part in parts for marker in _DEPRECATED_MARKERS)


def has_nc_files(directory: Path) -> bool:
    """Return whether a directory holds NetCDF files *directly* inside it."""
    return any(nc_files(directory, limit=1))


def nc_files(directory: Path, limit: int | None = None) -> list[Path]:
    """Return the NetCDF files directly inside a directory, sorted by name.

    Only the directory itself, never below it.  That is what tells a real
    experiment from the archive's stray directory trees: a couple of paths
    match the experiment naming but hold nothing but a ``Users/...``
    subdirectory, and those are not experiments.
    """
    found = []
    for entry in sorted(Path(directory).iterdir()):
        if entry.suffix == '.nc' and entry.is_file():
            found.append(entry)
            if limit is not None and len(found) >= limit:
                break
    return found


def find_experiments(root: Path) -> list[Path]:
    """Return every experiment directory under ``root``, sorted and unique.

    A directory qualifies when it sits below an experiment-set directory named
    *exactly* as ``data/config/experiment_sets.txt`` says (never ``old_CORE``,
    ``CORE_old`` or ``CESM2-WACCM_CORE``, which appear beside the real ones as
    abandoned copies), its own name is the configured prefix and a three-digit
    number in range, and it holds at least one NetCDF file directly inside it.
    """
    root = Path(root)
    sets_by_name = {s.name: s for s in experiment_sets()}
    found: set[Path] = set()
    # Directories already walked, by device and inode.  ``followlinks=True``
    # makes ``os.walk`` descend into symlinked directories, which is what lets
    # an alias root (a symlinked group, or a parent holding a symlinked
    # ``GrIS``) be searched at all -- but it also means a link pointing back up
    # the tree, or two names for one directory, would be walked once per name,
    # forever for a loop.  Pruning by (st_dev, st_ino) keeps the first
    # encounter (deterministic, because the walk is sorted) and drops the rest.
    seen: set[tuple[int, int]] = set()
    for base, dirs, _ in os.walk(root, topdown=True, followlinks=True):
        current = Path(base)
        keep = []
        for name in dirs:
            stat = (current / name).stat()
            key = (stat.st_dev, stat.st_ino)
            if key not in seen:
                seen.add(key)
                keep.append(name)
        dirs[:] = sorted(keep)
        experiment_set = sets_by_name.get(current.name)
        if experiment_set is None:
            continue
        if _has_deprecated_ancestor(current, root):
            continue
        for entry in sorted(current.iterdir()):
            if not entry.is_dir():
                continue
            if not experiment_set.matches(entry.name):
                continue
            if not has_nc_files(entry):
                continue
            found.add(entry)
    return sorted(found)


def parse_variable_filter(text: str | None) -> frozenset[str] | None:
    """Turn a ``--variables`` value into a set of names, or ``None`` for all.

    Surrounding whitespace is stripped from each name, so that
    ``--variables "lithk, acabf"`` means what it looks like it means.
    """
    if text is None:
        return None
    names = frozenset(name.strip() for name in text.split(',') if name.strip())
    return names or None


def variable_wanted(variable: str, wanted: frozenset[str] | None) -> bool:
    """Return whether a variable passes the ``--variables`` filter."""
    return wanted is None or variable in wanted


@dataclass(frozen=True)
class Subset:
    """Which groups, models, experiment sets and experiments to keep.

    Each part is ``None`` for "everything", or a set of exact names.  An
    experiment passes when every filter that is set matches the
    corresponding component of its group/model/experiment-set/experiment
    path, so the filters narrow jointly.
    """

    groups: frozenset[str] | None = None
    models: frozenset[str] | None = None
    sets: frozenset[str] | None = None
    experiments: frozenset[str] | None = None

    #: The path components each field filters, in the order they occur.
    _LEVELS = ('groups', 'models', 'sets', 'experiments')

    def matches(self, experiment_dir: Path) -> bool:
        """Return whether one experiment passes every filter that is set.

        The filters are read off the last four components of the experiment's
        path, which ``find_experiments`` guarantees are
        group/model/experiment-set/experiment: it only returns directories
        directly inside a set directory.  Working from the path tail rather
        than a position relative to the experiments root is what makes
        ``--groups`` work when the root is a group directory.
        """
        parts = Path(experiment_dir).parts[-EXPERIMENT_PATH_DEPTH:]
        # Right-aligned: an experiment reached through a shorter path, e.g. a
        # root sitting at the model level, still lines each name up with its
        # own filter, with the missing leading levels simply unchecked.
        for level, part in zip(reversed(self._LEVELS), reversed(parts)):
            wanted = getattr(self, level)
            if wanted is not None and part not in wanted:
                return False
        return True

    def summary(self) -> dict[str, str]:
        """Return each filter as a value for a report line, '(all)' if unset."""
        lines = {}
        for level in self._LEVELS:
            wanted = getattr(self, level)
            lines[level] = ('(all)' if wanted is None
                            else ','.join(sorted(wanted)))
        return lines


def parse_subset(groups: str | None, models: str | None, sets: str | None,
                 experiments: str | None) -> Subset | None:
    """Turn the ``--groups``/``--models``/``--sets``/``--experiments`` values
    into a :class:`Subset`, or ``None`` when no filter was given.

    Like ``--variables``, each value is comma-separated names with
    surrounding whitespace stripped.  ``None`` -- rather than a ``Subset``
    with every part unset -- is what keeps an unfiltered run from logging a
    no-match warning or writing ``(all)`` lines into ``summary.txt``.
    """
    subset = Subset(parse_variable_filter(groups),
                    parse_variable_filter(models),
                    parse_variable_filter(sets),
                    parse_variable_filter(experiments))
    if all(getattr(subset, level) is None for level in Subset._LEVELS):
        return None
    return subset


#: The option each :class:`Subset` level was given on the command line, for
#: error messages that name the option the user typed.
_LEVEL_OPTIONS = {'groups': '--groups', 'models': '--models',
                  'sets': '--sets', 'experiments': '--experiments'}


def filter_experiments(experiment_dirs: list[Path],
                       subset: Subset | None) -> list[Path]:
    """Keep only the experiments the subset selection asks for.

    The archive walk itself is not pruned: an inventory or run reads far more
    per experiment than the walk costs, and the found directories must stay
    in their stable sorted order.

    A requested name that matched no experiment raises :class:`ValueError`.
    On a long run, a typo such as ``--groups NORCE,AWl`` would otherwise
    silently drop AWl and regrid without it.
    """
    if subset is None:
        return experiment_dirs
    selected = [directory for directory in experiment_dirs
                if subset.matches(directory)]
    seen: dict[str, set[str]] = {level: set() for level in Subset._LEVELS}
    for directory in experiment_dirs:
        parts = Path(directory).parts[-EXPERIMENT_PATH_DEPTH:]
        for level, part in zip(reversed(Subset._LEVELS), reversed(parts)):
            seen[level].add(part)
    unmatched = []
    for level in Subset._LEVELS:
        wanted = getattr(subset, level)
        if wanted is None:
            continue
        missing = sorted(wanted - seen[level])
        if missing:
            unmatched.append(f'{_LEVEL_OPTIONS[level]} {",".join(missing)}')
    if unmatched:
        raise ValueError(
            'no experiment matches the selection: ' + '; '.join(unmatched))
    return selected


def experiment_rel_path(experiment_dir: Path,
                        experiments_root: Path | None) -> Path:
    """Return the path to mirror in the output for one experiment.

    Relative to ``experiments_root`` when the experiment is under it.  When it
    is not -- or no root was given -- the last
    :data:`EXPERIMENT_PATH_DEPTH` components are used instead, which is the
    group/model/experiment-set/experiment tail of a well-formed archive path.
    """
    experiment_dir = Path(experiment_dir)
    if experiments_root is not None:
        # abspath makes relative and absolute inputs comparable and resolves
        # '..' without following symlinks -- so an experiment reached through
        # a symlinked archive root still falls back, while a merely relative
        # path still matches.
        experiment_dir = Path(os.path.abspath(experiment_dir))
        experiments_root = Path(os.path.abspath(experiments_root))
        try:
            return experiment_dir.relative_to(experiments_root)
        except ValueError:
            pass
    parts = experiment_dir.parts[-EXPERIMENT_PATH_DEPTH:]
    fallback = Path(*parts)
    LOGGER.info(
        "'%s' is not under the experiments root; mirroring its last %d path "
        'components: %s', experiment_dir, EXPERIMENT_PATH_DEPTH, fallback)
    return fallback
