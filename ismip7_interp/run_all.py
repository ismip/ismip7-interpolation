"""Regridding every experiment found under an ISMIP7 archive root."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ismip7_interp import __version__, cli
from ismip7_interp.archive import (
    Subset,
    filter_experiments,
    find_experiments,
    parse_subset,
)
from ismip7_interp.experiment import _stamp, process_experiment, utc_now
from ismip7_interp.grids import res_dir_name

LOGGER = logging.getLogger(__name__)

#: Default pass rate below which the run as a whole is a failure.  Real
#: experiments vary in quality and some are expected not to process cleanly, so
#: a single failure is logged and stepped over; a run where most of the archive
#: failed is a different thing, and that is what this catches.
DEFAULT_MIN_PASS_PCT = 60


@dataclass
class RunReport:
    """What happened across a whole archive."""

    experiments_root: Path
    #: ``(status, path)`` pairs, in the order the experiments were processed.
    experiments: list[tuple[str, Path]] = field(default_factory=list)
    run_log: Path | None = None

    @property
    def n_total(self) -> int:
        """Return how many experiments were found."""
        return len(self.experiments)

    @property
    def n_passed(self) -> int:
        """Return how many experiments processed without a file failure."""
        return sum(1 for status, _ in self.experiments if status == 'OK')

    @property
    def pass_pct(self) -> int:
        """Return the percentage of experiments that passed, rounded down."""
        if self.n_total == 0:
            return 0
        return self.n_passed * 100 // self.n_total


def run_all_experiments(experiments_root: Path, output_root: Path, domain: str,
                        target_res: int, on_unchanged: str = 'symlink',
                        variables: list[str] | None = None,
                        weights_dir: Path | None = None,
                        min_pass_pct: int = DEFAULT_MIN_PASS_PCT,
                        verbose: bool = False,
                        subset: Subset | None = None) -> RunReport:
    """Regrid every experiment under ``experiments_root``.

    A failed experiment is logged and stepped over rather than ending the run.
    The returned report says how many passed; the caller decides what to do
    with a pass rate below ``min_pass_pct``.

    With ``subset`` given, only experiments matching every set filter are
    processed; the output tree keeps the full group/model/set/experiment
    paths, so a filtered run is indistinguishable in layout from a full one
    that found fewer experiments.
    """
    experiments_root = Path(experiments_root).resolve()
    experiment_dirs = find_experiments(experiments_root)
    selected = filter_experiments(experiment_dirs, subset)
    if not selected:
        if subset is not None and experiment_dirs:
            # "No experiments found" would read as an empty archive, when the
            # archive was fine and the selection kept none of it.
            raise FileNotFoundError(
                f'the subset selection matched none of the '
                f'{len(experiment_dirs)} experiment(s) found under '
                f'{experiments_root}')
        raise FileNotFoundError(
            f'no experiments found under {experiments_root} -- checked '
            f'against the experiment sets this package is configured for')
    LOGGER.info('found %d experiment(s) under %s', len(selected),
                experiments_root)

    started = utc_now()
    report = RunReport(experiments_root)
    for experiment_dir in selected:
        LOGGER.info('=== processing experiment: %s ===', experiment_dir)
        try:
            result = process_experiment(
                experiment_dir, output_root, domain, target_res,
                experiments_root=experiments_root, on_unchanged=on_unchanged,
                variables=variables, weights_dir=weights_dir,
                verbose=verbose)
        except cli.EXPECTED_ERRORS as error:
            LOGGER.error('FAIL experiment %s: %s', experiment_dir, error)
            report.experiments.append(('FAIL', experiment_dir))
            continue
        if result.succeeded:
            report.experiments.append(('OK', experiment_dir))
        else:
            LOGGER.error('FAIL experiment %s: %d file(s) failed',
                         experiment_dir, result.n_failed)
            report.experiments.append(('FAIL', experiment_dir))

    report.run_log = _write_run_log(
        Path(output_root) / res_dir_name(domain, target_res) / 'logs', report,
        domain, target_res, on_unchanged, variables, subset, min_pass_pct,
        started)
    LOGGER.info('done: %d/%d experiment(s) passed (%d%%) -- output under %s, '
                'run log at %s', report.n_passed, report.n_total,
                report.pass_pct,
                Path(output_root) / res_dir_name(domain, target_res),
                report.run_log)
    return report


def _write_run_log(logs_dir: Path, report: RunReport, domain: str,
                   target_res: int, on_unchanged: str, variables: list[str] | None,
                   subset: Subset | None, min_pass_pct: int,
                   started: datetime) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    run_log = logs_dir / f'run_{started.strftime("%Y%m%dT%H%M%SZ")}.log'
    fields = [
        ('domain', domain),
        ('target_res_m', target_res),
        ('experiments_root', report.experiments_root),
        ('on_unchanged', on_unchanged),
        ('variables', ' '.join(variables) if variables else '(all)'),
    ]
    if subset is not None:
        fields += list(subset.summary().items())
    fields += [
        ('min_pass_pct', min_pass_pct),
        ('version', __version__),
        ('started_utc', _stamp(started)),
        ('finished_utc', _stamp(utc_now())),
        ('experiments_total', report.n_total),
        ('experiments_passed', report.n_passed),
        ('pass_pct', report.pass_pct),
    ]
    lines = [f'{name + ":":<19} {value}' for name, value in fields]
    lines += [
        '--- per-experiment results (each experiment has its own file-level '
        'log in this directory) ---',
    ]
    lines += [f'{status:<4} {path}' for status, path in report.experiments]
    run_log.write_text('\n'.join(lines) + '\n')
    return run_log


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='ismip7-run-all',
        description=__doc__,
        epilog='A failing experiment is logged and skipped; the run as a '
               'whole fails only if fewer than --min-pass-pct percent of '
               'experiments succeed.')
    cli.add_common_arguments(parser)
    cli.add_grid_arguments(parser)
    cli.add_experiments_root_argument(parser)
    parser.add_argument(
        '--output-root', type=Path, default=Path.cwd() / 'output',
        metavar='DIR',
        help='where to write the regridded output tree (default: '
             '%(default)s)')
    cli.add_on_unchanged_argument(parser)
    cli.add_variables_argument(parser)
    cli.add_weights_argument(parser)
    cli.add_subset_arguments(parser)
    parser.add_argument(
        '--min-pass-pct', type=cli.percentage,
        default=DEFAULT_MIN_PASS_PCT, metavar='PCT',
        help='fail the run if fewer than this percentage of experiments '
             'succeed (default: %(default)s)')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``ismip7-run-all``."""
    args = _parse_args(argv)
    cli.configure_logging(args.verbose)

    def work() -> int:
        root = cli.resolve_experiments_root(args.experiments_root, args.domain)
        subset = parse_subset(args.groups, args.models, args.sets,
                              args.experiments)
        report = run_all_experiments(
            root, args.output_root, args.domain, args.target_res,
            on_unchanged=args.on_unchanged, variables=args.variables,
            weights_dir=args.weights_dir, min_pass_pct=args.min_pass_pct,
            verbose=args.verbose > 0, subset=subset)
        if report.pass_pct < args.min_pass_pct:
            LOGGER.error('pass rate %d%% is below --min-pass-pct %d%%',
                         report.pass_pct, args.min_pass_pct)
            return 1
        return 0

    return cli.run_main(work)


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
