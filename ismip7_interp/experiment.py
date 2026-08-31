"""Regridding every variable file in one ISMIP7 experiment directory."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ismip7_interp import __version__, cli
from ismip7_interp.archive import (
    experiment_rel_path,
    nc_files,
    parse_variable_filter,
    variable_wanted,
)
from ismip7_interp.grids import res_dir_name
from ismip7_interp.interpolate import interpolate_file
from ismip7_interp.variables import var_from_filename

LOGGER = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return the current UTC time, as one place for the tests to freeze."""
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ')


@dataclass
class ExperimentReport:
    """What happened to one experiment."""

    experiment_dir: Path
    rel_path: Path
    out_dir: Path
    #: ``(status, filename)`` pairs, in the order the files were processed.
    files: list[tuple[str, str]] = field(default_factory=list)
    log_file: Path | None = None

    @property
    def n_total(self) -> int:
        """Return how many files were considered."""
        return len(self.files)

    @property
    def n_failed(self) -> int:
        """Return how many files failed."""
        return sum(1 for status, _ in self.files if status == 'FAIL')

    @property
    def succeeded(self) -> bool:
        """Return whether every file that was considered was processed."""
        return self.n_failed == 0


def process_experiment(experiment_dir: Path, output_root: Path, domain: str,
                       target_res: int, experiments_root: Path | None = None,
                       on_unchanged: str = 'symlink',
                       variables: str | None = None,
                       weights_dir: Path | None = None,
                       verbose: bool = False) -> ExperimentReport:
    """Regrid every NetCDF file in one experiment directory.

    Output goes to ``output_root/<DOMAIN>_<res>m/<mirrored path>``, where the
    mirrored path is the experiment's path relative to ``experiments_root``.
    Filenames are unchanged: the resolution lives in the one top-level
    directory, not in every name.

    A timestamped log recording what was processed is written to
    ``output_root/<DOMAIN>_<res>m/logs/`` -- including when the
    ``--variables`` filter matched nothing, since "this experiment has none of
    the variables you asked for" is a result worth having on disk rather than
    an absence to puzzle over later.
    """
    experiment_dir = Path(experiment_dir).resolve()
    if not experiment_dir.is_dir():
        raise NotADirectoryError(
            f'experiment directory not found: {experiment_dir}')

    started = utc_now()
    rel_path = experiment_rel_path(experiment_dir, experiments_root)
    res_dir = Path(output_root) / res_dir_name(domain, target_res)
    out_dir = res_dir / rel_path
    logs_dir = res_dir / 'logs'

    found = nc_files(experiment_dir)
    if not found:
        raise FileNotFoundError(f'no .nc files found in {experiment_dir}')

    wanted = parse_variable_filter(variables)
    selected = [path for path in found
                if variable_wanted(var_from_filename(path), wanted)]

    report = ExperimentReport(experiment_dir, rel_path, out_dir)
    if not selected:
        LOGGER.info('no files matching --variables %s in %s -- nothing to do',
                    variables, experiment_dir)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        for in_file in selected:
            try:
                interpolate_file(in_file, out_dir / in_file.name, domain,
                                 target_res, on_unchanged=on_unchanged,
                                 weights_dir=weights_dir, verbose=verbose)
            except cli.EXPECTED_ERRORS as error:
                LOGGER.error('FAIL %s: %s', in_file.name, error)
                report.files.append(('FAIL', in_file.name))
            else:
                report.files.append(('OK', in_file.name))

    report.log_file = _write_log(logs_dir, report, domain, target_res,
                                 on_unchanged, variables, started)
    LOGGER.info('done: %d file(s) processed, %d failed -- output in %s, log '
                'at %s', report.n_total, report.n_failed, out_dir,
                report.log_file)
    return report


def _write_log(logs_dir: Path, report: ExperimentReport, domain: str,
               target_res: int, on_unchanged: str, variables: str | None,
               started: datetime) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    name = str(report.rel_path).replace('/', '_')
    log_file = logs_dir / f'{name}_{started.strftime("%Y%m%dT%H%M%SZ")}.log'
    lines = [
        f'experiment_dir: {report.experiment_dir}',
        f'rel_path:       {report.rel_path}',
        f'domain:         {domain}',
        f'target_res_m:   {target_res}',
        f'on_unchanged:   {on_unchanged}',
        f'variables:      {variables or "(all)"}',
        f'version:        {__version__}',
        f'started_utc:    {_stamp(started)}',
        f'finished_utc:   {_stamp(utc_now())}',
        f'files_total:    {report.n_total}',
        f'files_failed:   {report.n_failed}',
        '--- per-file results ---',
    ]
    lines += [f'{status:<4} {name}' for status, name in report.files]
    log_file.write_text('\n'.join(lines) + '\n')
    return log_file


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='ismip7-process-experiment',
        description=__doc__,
        epilog='An experiment that has none of the requested --variables is '
               'not an error: some variables are optional and legitimately '
               'absent.')
    cli.add_common_arguments(parser)
    cli.add_grid_arguments(parser)
    cli.add_experiments_root_argument(parser)
    cli.add_on_unchanged_argument(parser)
    cli.add_variables_argument(parser)
    cli.add_weights_argument(parser)
    parser.add_argument('experiment_dir', type=Path, metavar='EXPERIMENT_DIR',
                        help='the experiment directory to regrid')
    parser.add_argument('output_root', type=Path, metavar='OUTPUT_ROOT',
                        help='where to write the regridded output tree')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``ismip7-process-experiment``."""
    args = _parse_args(argv)
    cli.configure_logging(args.verbose)

    def work() -> int:
        report = process_experiment(
            args.experiment_dir, args.output_root, args.domain,
            args.target_res, experiments_root=args.experiments_root,
            on_unchanged=args.on_unchanged, variables=args.variables,
            weights_dir=args.weights_dir, verbose=args.verbose > 0)
        return 0 if report.succeeded else 1

    return cli.run_main(work)


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
