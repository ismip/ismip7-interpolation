"""Processing one experiment directory, and the log it leaves behind."""

from __future__ import annotations

from pathlib import Path

import pytest

from ismip7_interp.cdo import CdoError
from ismip7_interp.experiment import (
    ExperimentReport,
    main,
    process_experiment,
)
from ismip7_interp.interpolate import Result

from conftest import NAME_TAIL, TARGET_RES

VARIABLES = ('lithk', 'acabf', 'lim')


@pytest.fixture
def experiment(tmp_path):
    """An archive with one experiment holding three variables."""
    directory = tmp_path / 'archive/GroupA/ModelA/CORE/C001'
    directory.mkdir(parents=True)
    for variable in VARIABLES:
        (directory / f'{variable}_{NAME_TAIL}').write_bytes(b'data')
    return directory


class Interpolations:
    """A stand-in for the regridding, recording what it was asked to do."""

    def __init__(self):
        self.calls: list[tuple[Path, Path]] = []
        #: Variables to fail on, so a partial failure can be exercised.
        self.fails: set[str] = set()

    def __call__(self, in_file, out_file, domain, target_res, method='auto',
                 on_unchanged='symlink', weights_dir=None, verbose=False):
        variable = Path(in_file).name.split('_')[0]
        if variable in self.fails:
            raise CdoError(f'{variable} is broken')
        self.calls.append((Path(in_file), Path(out_file)))
        Path(out_file).parent.mkdir(parents=True, exist_ok=True)
        Path(out_file).write_bytes(b'regridded')
        return Result('regridded', variable, 16000, 'ycon')


@pytest.fixture
def interpolated(monkeypatch):
    """Replace the regridding, so these tests are about the driver alone."""
    recorder = Interpolations()
    monkeypatch.setattr('ismip7_interp.experiment.interpolate_file', recorder)
    return recorder


def test_output_mirrors_the_archive_below_one_resolution_directory(
        tmp_path, experiment, interpolated):
    report = process_experiment(experiment, tmp_path / 'out', 'GrIS',
                                TARGET_RES,
                                experiments_root=tmp_path / 'archive')
    assert report.out_dir == (tmp_path / 'out' / 'GrIS_08000m'
                              / 'GroupA/ModelA/CORE/C001')
    assert report.succeeded


def test_output_filenames_are_unchanged(tmp_path, experiment, interpolated):
    """The resolution lives in the top directory, not in every filename."""
    process_experiment(experiment, tmp_path / 'out', 'GrIS', TARGET_RES,
                       experiments_root=tmp_path / 'archive')
    out_dir = tmp_path / 'out/GrIS_08000m/GroupA/ModelA/CORE/C001'
    written = {path.name for path in out_dir.iterdir()}
    assert written == {f'{variable}_{NAME_TAIL}' for variable in VARIABLES}


def test_every_file_is_processed(tmp_path, experiment, interpolated):
    report = process_experiment(experiment, tmp_path / 'out', 'GrIS',
                                TARGET_RES,
                                experiments_root=tmp_path / 'archive')
    assert report.n_total == len(VARIABLES)
    assert report.n_failed == 0


def test_files_are_processed_in_a_stable_order(tmp_path, experiment,
                                               interpolated):
    """A log that reorders itself between runs cannot be diffed."""
    process_experiment(experiment, tmp_path / 'out', 'GrIS', TARGET_RES,
                       experiments_root=tmp_path / 'archive')
    names = [name for _status, name in
             process_experiment(experiment, tmp_path / 'out2', 'GrIS',
                                TARGET_RES,
                                experiments_root=tmp_path / 'archive').files]
    assert names == sorted(names)


def test_one_failing_file_does_not_stop_the_others(tmp_path, experiment,
                                                   interpolated):
    interpolated.fails.add('acabf')
    report = process_experiment(experiment, tmp_path / 'out', 'GrIS',
                                TARGET_RES,
                                experiments_root=tmp_path / 'archive')
    assert report.n_total == 3
    assert report.n_failed == 1
    assert not report.succeeded
    assert ('FAIL', f'acabf_{NAME_TAIL}') in report.files


def test_the_variables_filter_selects_files(tmp_path, experiment,
                                            interpolated):
    report = process_experiment(experiment, tmp_path / 'out', 'GrIS',
                                TARGET_RES,
                                experiments_root=tmp_path / 'archive',
                                variables='lithk')
    assert [name for _status, name in report.files] == [f'lithk_{NAME_TAIL}']


def test_the_variables_filter_tolerates_spaces(tmp_path, experiment,
                                               interpolated):
    report = process_experiment(experiment, tmp_path / 'out', 'GrIS',
                                TARGET_RES,
                                experiments_root=tmp_path / 'archive',
                                variables='lithk, acabf')
    assert report.n_total == 2


def test_no_matching_variables_is_not_a_failure(tmp_path, experiment,
                                                interpolated):
    """Some variables are optional and legitimately absent."""
    report = process_experiment(experiment, tmp_path / 'out', 'GrIS',
                                TARGET_RES,
                                experiments_root=tmp_path / 'archive',
                                variables='orog')
    assert report.succeeded
    assert report.n_total == 0


def test_a_log_is_written_even_when_nothing_matched(tmp_path, experiment,
                                                    interpolated):
    """"None of them are here" is a result, not an absence."""
    report = process_experiment(experiment, tmp_path / 'out', 'GrIS',
                                TARGET_RES,
                                experiments_root=tmp_path / 'archive',
                                variables='orog')
    assert report.log_file.is_file()
    assert 'files_total:    0' in report.log_file.read_text()


def test_the_log_records_the_run(tmp_path, experiment, interpolated):
    report = process_experiment(experiment, tmp_path / 'out', 'GrIS',
                                TARGET_RES,
                                experiments_root=tmp_path / 'archive',
                                on_unchanged='copy')
    text = report.log_file.read_text()
    assert 'domain:         GrIS' in text
    assert 'target_res_m:   8000' in text
    assert 'on_unchanged:   copy' in text
    assert 'variables:      (all)' in text
    assert 'files_total:    3' in text
    assert 'files_failed:   0' in text
    for variable in VARIABLES:
        assert f'OK   {variable}_{NAME_TAIL}' in text


def test_the_log_records_the_version(tmp_path, experiment, interpolated):
    """A regridded archive must say what produced it."""
    from ismip7_interp import __version__

    report = process_experiment(experiment, tmp_path / 'out', 'GrIS',
                                TARGET_RES,
                                experiments_root=tmp_path / 'archive')
    assert f'version:        {__version__}' in report.log_file.read_text()


def test_the_log_lands_beside_the_output_not_inside_it(tmp_path, experiment,
                                                       interpolated):
    report = process_experiment(experiment, tmp_path / 'out', 'GrIS',
                                TARGET_RES,
                                experiments_root=tmp_path / 'archive')
    assert report.log_file.parent == tmp_path / 'out/GrIS_08000m/logs'


def test_the_log_name_identifies_the_experiment(tmp_path, experiment,
                                                interpolated):
    """All the logs share one directory, so their names must not collide."""
    report = process_experiment(experiment, tmp_path / 'out', 'GrIS',
                                TARGET_RES,
                                experiments_root=tmp_path / 'archive')
    assert report.log_file.name.startswith('GroupA_ModelA_CORE_C001_')


def test_an_experiment_with_no_files_is_reported(tmp_path, interpolated):
    empty = tmp_path / 'archive/GroupA/ModelA/CORE/C001'
    empty.mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match='no .nc files'):
        process_experiment(empty, tmp_path / 'out', 'GrIS', TARGET_RES)


def test_a_missing_experiment_directory_is_reported(tmp_path):
    with pytest.raises(NotADirectoryError):
        process_experiment(tmp_path / 'absent', tmp_path / 'out', 'GrIS',
                           TARGET_RES)


def test_report_counts():
    report = ExperimentReport(Path('a'), Path('b'), Path('c'))
    report.files = [('OK', 'one.nc'), ('FAIL', 'two.nc'), ('OK', 'three.nc')]
    assert report.n_total == 3
    assert report.n_failed == 1
    assert not report.succeeded


def test_main_returns_nonzero_when_a_file_fails(tmp_path, experiment,
                                                interpolated):
    interpolated.fails.add('lithk')
    status = main(['--domain', 'GrIS', '--target-res', str(TARGET_RES),
                   '--experiments-root', str(tmp_path / 'archive'),
                   str(experiment), str(tmp_path / 'out')])
    assert status == 1


def test_main_returns_zero_on_success(tmp_path, experiment, interpolated):
    status = main(['--domain', 'GrIS', '--target-res', str(TARGET_RES),
                   '--experiments-root', str(tmp_path / 'archive'),
                   str(experiment), str(tmp_path / 'out')])
    assert status == 0


def test_main_reports_a_missing_directory_as_a_status(tmp_path):
    status = main(['--domain', 'GrIS', '--target-res', str(TARGET_RES),
                   str(tmp_path / 'absent'), str(tmp_path / 'out')])
    assert status == 1
