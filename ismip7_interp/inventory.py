"""A read-only report on what an ISMIP7 archive holds.

Per file and per experiment: actual size, a *predicted* size after regridding
to a target resolution, and completeness against the mandatory variables of
the ISMIP7 data request.  Nothing is regridded and no data is read -- only file
sizes and NetCDF headers -- so this is cheap enough to run over a whole archive
and safe to run against a read-only one.

The predicted size is a ballpark, not a promise: the actual size scaled by the
ratio of target to source grid points.  It ignores header overhead,
compression and per-variable data types.
"""

from __future__ import annotations

import argparse
import csv
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ismip7_interp import __version__, cli
from ismip7_interp.archive import (
    find_experiments,
    nc_files,
    parse_variable_filter,
    variable_wanted,
)
from ismip7_interp.experiment import _stamp, utc_now
from ismip7_interp.grids import detect_res_from_dims, gdf_dims, gdf_path
from ismip7_interp.ncfile import NetCDFError, file_size, header_grid_dims
from ismip7_interp.variables import mandatory_variables, var_from_filename

LOGGER = logging.getLogger(__name__)

#: What a file turned out to be.
UNREADABLE = 'unreadable'
SCALAR = 'scalar'
SPATIAL = 'spatial'

#: What an experiment would need if it were regridded.
ALREADY_AT_TARGET = 'already_at_target'
NEEDS_REGRID = 'needs_regrid'
UNKNOWN_GRID = 'unknown_grid'
NO_SPATIAL_DATA = 'no_spatial_data'

#: Written for a size that cannot be predicted.
NOT_AVAILABLE = 'NA'

FILE_COLUMNS = ('experiment', 'variable', 'mandatory', 'kind', 'source_res_m',
                'actual_bytes', 'predicted_target_bytes')
EXPERIMENT_COLUMNS = ('experiment', 'n_files', 'n_mandatory_expected',
                      'n_mandatory_present', 'missing_mandatory',
                      'total_actual_bytes', 'total_predicted_bytes',
                      'regrid_status')


@dataclass
class FileRow:
    """One row of ``files.csv``."""

    experiment: Path
    variable: str
    mandatory: bool
    kind: str
    source_res: int | None
    actual_bytes: int
    predicted_bytes: int | None

    def as_row(self) -> dict[str, object]:
        """Return this row as the mapping the CSV writer takes."""
        return {
            'experiment': str(self.experiment),
            'variable': self.variable,
            'mandatory': 'yes' if self.mandatory else 'no',
            'kind': self.kind,
            'source_res_m': '' if self.source_res is None else self.source_res,
            'actual_bytes': self.actual_bytes,
            'predicted_target_bytes': (
                NOT_AVAILABLE if self.predicted_bytes is None
                else self.predicted_bytes),
        }


@dataclass
class ExperimentRow:
    """One row of ``experiments.csv``."""

    experiment: Path
    n_files: int
    n_mandatory_expected: int
    missing_mandatory: list[str]
    total_actual_bytes: int
    total_predicted_bytes: int
    regrid_status: str

    @property
    def n_mandatory_present(self) -> int:
        """Return how many of the expected mandatory variables were found."""
        return self.n_mandatory_expected - len(self.missing_mandatory)

    def as_row(self) -> dict[str, object]:
        """Return this row as the mapping the CSV writer takes."""
        return {
            'experiment': str(self.experiment),
            'n_files': self.n_files,
            'n_mandatory_expected': self.n_mandatory_expected,
            'n_mandatory_present': self.n_mandatory_present,
            'missing_mandatory': ';'.join(self.missing_mandatory),
            'total_actual_bytes': self.total_actual_bytes,
            'total_predicted_bytes': self.total_predicted_bytes,
            'regrid_status': self.regrid_status,
        }


@dataclass
class Inventory:
    """The whole scan."""

    files: list[FileRow] = field(default_factory=list)
    experiments: list[ExperimentRow] = field(default_factory=list)

    @property
    def status_counts(self) -> Counter:
        """Return how many experiments fell into each regrid status."""
        return Counter(row.regrid_status for row in self.experiments)


def default_output_dir(domain: str) -> Path:
    """Return where a scan writes when ``--output`` is not given.

    Per domain, so that scanning GrIS and then AIS does not overwrite the
    first scan with the second.
    """
    return Path.cwd() / 'inventory' / domain


def scan_experiment(experiment_dir: Path, domain: str, target_points: int,
                    target_res: int, expected_mandatory: frozenset[str],
                    wanted: frozenset[str] | None) -> tuple[
                        list[FileRow], ExperimentRow]:
    """Scan one experiment, returning its file rows and its summary row."""
    rows: list[FileRow] = []
    present: set[str] = set()
    total_actual = 0
    total_predicted = 0
    kinds: Counter = Counter()

    for path in nc_files(experiment_dir):
        variable = var_from_filename(path)
        if not variable_wanted(variable, wanted):
            continue
        present.add(variable)
        actual_bytes = file_size(path)
        total_actual += actual_bytes

        source_res: int | None = None
        predicted: int | None = None
        try:
            dims = header_grid_dims(path)
        except NetCDFError as error:
            # One unreadable file must not end the scan of the archive: an
            # inventory that stops at the first bad file is exactly the
            # inventory you cannot use to find the bad files.
            LOGGER.warning('%s', error)
            kind = UNREADABLE
        else:
            if dims is None:
                kind = SCALAR
                # A file with no grid is placed unchanged, so its size after
                # regridding is its size now.
                predicted = actual_bytes
            else:
                kind = SPATIAL
                source_res = detect_res_from_dims(domain, dims)
                if source_res is None:
                    kinds['unknown'] += 1
                else:
                    predicted = actual_bytes * target_points // (
                        dims[0] * dims[1])
                    kinds['on_target' if source_res == target_res
                          else 'off_target'] += 1
        if predicted is not None:
            total_predicted += predicted
        rows.append(FileRow(experiment_dir, variable,
                            variable in expected_mandatory, kind, source_res,
                            actual_bytes, predicted))

    if kinds['unknown']:
        status = UNKNOWN_GRID
    elif kinds['off_target']:
        status = NEEDS_REGRID
    elif kinds['on_target']:
        status = ALREADY_AT_TARGET
    else:
        status = NO_SPATIAL_DATA

    summary = ExperimentRow(
        experiment_dir, len(rows), len(expected_mandatory),
        sorted(expected_mandatory - present), total_actual, total_predicted,
        status)
    return rows, summary


def inventory_archive(experiments_root: Path, output_dir: Path, domain: str,
                      target_res: int,
                      variables: str | None = None) -> Inventory:
    """Scan an archive, writing the two CSVs and the summary.

    With ``variables`` given, every other file is skipped outright rather than
    filtered out of the report, which is a real speedup and not just a smaller
    report.  Mandatory-variable completeness is narrowed to match: only
    requested variables that are also mandatory are expected, so a filtered
    scan does not report the variables it never looked at as missing.
    """
    experiments_root = Path(experiments_root).resolve()
    output_dir = Path(output_dir)
    started = utc_now()

    target_points = _grid_points(domain, target_res)
    wanted = parse_variable_filter(variables)
    expected_mandatory = mandatory_variables()
    if wanted is not None:
        expected_mandatory = frozenset(expected_mandatory & wanted)

    inventory = Inventory()
    for number, experiment_dir in enumerate(
            find_experiments(experiments_root), start=1):
        LOGGER.info('[%d] scanning %s', number, experiment_dir)
        rows, summary = scan_experiment(experiment_dir, domain, target_points,
                                        target_res, expected_mandatory, wanted)
        inventory.files.extend(rows)
        inventory.experiments.append(summary)

    _write_inventory(inventory, output_dir, experiments_root, domain,
                     target_res, variables, started)
    counts = inventory.status_counts
    LOGGER.info('done: %d experiment(s) scanned (%d already at target, '
                '%d need regrid, %d unknown grid, %d no spatial data) -- '
                'written to %s',
                len(inventory.experiments), counts[ALREADY_AT_TARGET],
                counts[NEEDS_REGRID], counts[UNKNOWN_GRID],
                counts[NO_SPATIAL_DATA], output_dir)
    return inventory


def _grid_points(domain: str, res_m: int) -> int:
    xsize, ysize = gdf_dims(gdf_path(domain, res_m))
    return xsize * ysize


def _write_inventory(inventory: Inventory, output_dir: Path,
                     experiments_root: Path, domain: str, target_res: int,
                     variables: str | None, started: datetime) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    # newline='' and csv.DictWriter, not manual string joining: an archive path
    # is free to contain a comma, and one that did would silently shift every
    # later column of that row.
    with open(output_dir / 'files.csv', 'w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FILE_COLUMNS)
        writer.writeheader()
        for row in inventory.files:
            writer.writerow(row.as_row())
    with open(output_dir / 'experiments.csv', 'w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPERIMENT_COLUMNS)
        writer.writeheader()
        for row in inventory.experiments:
            writer.writerow(row.as_row())

    counts = inventory.status_counts
    (output_dir / 'summary.txt').write_text('\n'.join([
        f'domain:             {domain}',
        f'target_res_m:       {target_res}',
        f'experiments_root:   {experiments_root}',
        f'variables:          {variables or "(all)"}',
        f'version:            {__version__}',
        f'scanned_utc:        {_stamp(started)}',
        f'experiments_total:  {len(inventory.experiments)}',
        f'already_at_target:  {counts[ALREADY_AT_TARGET]}',
        f'needs_regrid:       {counts[NEEDS_REGRID]}',
        f'unknown_grid:       {counts[UNKNOWN_GRID]}',
        f'no_spatial_data:    {counts[NO_SPATIAL_DATA]}',
    ]) + '\n')


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='ismip7-inventory',
        description=__doc__,
        epilog='Nothing is regridded and no data is read, so this is safe to '
               'run against a read-only archive.')
    cli.add_common_arguments(parser)
    cli.add_grid_arguments(parser)
    cli.add_experiments_root_argument(parser)
    parser.add_argument(
        '--output', type=Path, metavar='DIR',
        help='where to write files.csv, experiments.csv and summary.txt; '
             'defaults to ./inventory/<domain>')
    cli.add_variables_argument(parser)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``ismip7-inventory``."""
    args = _parse_args(argv)
    cli.configure_logging(args.verbose)

    def work() -> int:
        root = cli.resolve_experiments_root(args.experiments_root, args.domain)
        output = args.output or default_output_dir(args.domain)
        inventory_archive(root, output, args.domain, args.target_res,
                          variables=args.variables)
        return 0

    return cli.run_main(work)


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
