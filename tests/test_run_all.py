"""Regridding a whole archive, and when a run as a whole counts as failed."""

from __future__ import annotations

from pathlib import Path

import pytest

from ismip7_interp.cdo import CdoError
from ismip7_interp.experiment import ExperimentReport
from ismip7_interp.run_all import RunReport, main, run_all_experiments

from conftest import NAME_TAIL, TARGET_RES


@pytest.fixture
def archive(tmp_path, make_archive):
    """An archive of five experiments across two groups."""
    root = tmp_path / 'archive'
    make_archive(root, {
        f'GroupA/ModelA/CORE/C00{number}': [f'lithk_{NAME_TAIL}']
        for number in range(1, 4)
    } | {
        f'GroupB/ModelB/CORE/C00{number}': [f'lithk_{NAME_TAIL}']
        for number in range(1, 3)
    })
    return root


class Experiments:
    """A stand-in for per-experiment processing, recording what it saw."""

    def __init__(self):
        self.seen: list[Path] = []
        #: Experiment directory names whose files should fail.
        self.fails: set[str] = set()
        #: Experiment directory names that should raise outright.
        self.raises: set[str] = set()

    def __call__(self, experiment_dir, output_root, domain, target_res,
                 experiments_root=None, on_unchanged='symlink',
                 variables=None, weights_dir=None, verbose=False):
        experiment_dir = Path(experiment_dir)
        self.seen.append(experiment_dir)
        if experiment_dir.name in self.raises:
            raise CdoError(f'{experiment_dir} is unreadable')
        report = ExperimentReport(experiment_dir, Path(experiment_dir.name),
                                  Path(output_root))
        status = 'FAIL' if experiment_dir.name in self.fails else 'OK'
        report.files = [(status, 'lithk.nc')]
        return report


@pytest.fixture
def processed(monkeypatch):
    recorder = Experiments()
    monkeypatch.setattr('ismip7_interp.run_all.process_experiment', recorder)
    return recorder


def test_every_experiment_is_processed(tmp_path, archive, processed):
    report = run_all_experiments(archive, tmp_path / 'out', 'GrIS',
                                 TARGET_RES)
    assert report.n_total == 5
    assert report.n_passed == 5
    assert report.pass_pct == 100


def test_experiments_are_processed_in_a_stable_order(tmp_path, archive,
                                                     processed):
    run_all_experiments(archive, tmp_path / 'out', 'GrIS', TARGET_RES)
    assert processed.seen == sorted(processed.seen)


def test_a_failing_experiment_does_not_stop_the_run(tmp_path, archive,
                                                    processed):
    """Real experiments vary in quality; one bad one does not end a run."""
    # C002 exists under both groups, so two of the five fail.
    processed.fails.add('C002')
    report = run_all_experiments(archive, tmp_path / 'out', 'GrIS',
                                 TARGET_RES)
    assert len(processed.seen) == 5
    assert report.n_passed == 3


def test_an_experiment_that_raises_does_not_stop_the_run(tmp_path, archive,
                                                         processed):
    processed.raises.add('C001')
    report = run_all_experiments(archive, tmp_path / 'out', 'GrIS',
                                 TARGET_RES)
    assert len(processed.seen) == 5
    # C001 exists under both groups, so both of those fail.
    assert report.n_passed == 3


def test_an_archive_with_no_experiments_is_reported(tmp_path, processed):
    empty = tmp_path / 'empty'
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match='no experiments found'):
        run_all_experiments(empty, tmp_path / 'out', 'GrIS', TARGET_RES)


def test_the_run_log_records_the_outcome(tmp_path, archive, processed):
    processed.fails.add('C003')
    report = run_all_experiments(archive, tmp_path / 'out', 'GrIS',
                                 TARGET_RES, min_pass_pct=50)
    text = report.run_log.read_text()
    assert 'domain:             GrIS' in text
    assert 'experiments_total:  5' in text
    assert 'experiments_passed: 4' in text
    assert 'pass_pct:           80' in text
    assert 'min_pass_pct:       50' in text


def test_the_run_log_sits_beside_the_per_experiment_logs(tmp_path, archive,
                                                         processed):
    report = run_all_experiments(archive, tmp_path / 'out', 'GrIS',
                                 TARGET_RES)
    assert report.run_log.parent == tmp_path / 'out/GrIS_08000m/logs'


@pytest.mark.parametrize('n_passed, n_total, expected', [
    (5, 5, 100),
    (4, 5, 80),
    (0, 5, 0),
    # Rounded down, so a threshold is never met by rounding up to it.
    (2, 3, 66),
])
def test_pass_pct(n_passed, n_total, expected):
    report = RunReport(Path('root'))
    report.experiments = ([('OK', Path('x'))] * n_passed
                          + [('FAIL', Path('y'))] * (n_total - n_passed))
    assert report.pass_pct == expected


def test_pass_pct_of_an_empty_run_does_not_divide_by_zero():
    assert RunReport(Path('root')).pass_pct == 0


def test_main_fails_below_the_threshold(tmp_path, archive, processed):
    processed.fails.update({'C001', 'C002', 'C003'})
    status = main(['--domain', 'GrIS', '--target-res', str(TARGET_RES),
                   '--experiments-root', str(archive),
                   '--output-root', str(tmp_path / 'out'),
                   '--min-pass-pct', '60'])
    # C001 and C002 exist under both groups: 4 of 5 fail, so 20% pass.
    assert status == 1


def test_main_passes_above_the_threshold(tmp_path, archive, processed):
    processed.fails.add('C003')
    status = main(['--domain', 'GrIS', '--target-res', str(TARGET_RES),
                   '--experiments-root', str(archive),
                   '--output-root', str(tmp_path / 'out'),
                   '--min-pass-pct', '60'])
    assert status == 0


def test_main_reports_a_missing_archive_root_as_a_status(tmp_path):
    status = main(['--domain', 'GrIS', '--target-res', str(TARGET_RES),
                   '--experiments-root', str(tmp_path / 'absent'),
                   '--output-root', str(tmp_path / 'out')])
    assert status == 1


def test_main_rejects_a_percentage_out_of_range(tmp_path, archive):
    with pytest.raises(SystemExit):
        main(['--domain', 'GrIS', '--target-res', str(TARGET_RES),
              '--experiments-root', str(archive), '--min-pass-pct', '150'])


def test_the_variables_filter_reaches_every_experiment(tmp_path, archive,
                                                       monkeypatch):
    seen = []

    def record(experiment_dir, output_root, domain, target_res,
               experiments_root=None, on_unchanged='symlink', variables=None,
               weights_dir=None, verbose=False):
        seen.append(variables)
        report = ExperimentReport(Path(experiment_dir), Path('rel'),
                                  Path(output_root))
        report.files = [('OK', 'lithk.nc')]
        return report

    monkeypatch.setattr('ismip7_interp.run_all.process_experiment', record)
    run_all_experiments(archive, tmp_path / 'out', 'GrIS', TARGET_RES,
                        variables='lithk')
    assert seen == ['lithk'] * 5
