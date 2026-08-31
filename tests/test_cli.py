"""The command-line surface: entry points, options, and CDO's absence."""

from __future__ import annotations

import subprocess
import sys
from importlib import metadata

import pytest

from ismip7_interp import __version__, cli
from ismip7_interp.__main__ import COMMANDS
from ismip7_interp.cdo import CdoNotFoundError, require_cdo, run_cdo

ENTRY_POINTS = {
    'ismip7-interpolate': 'ismip7_interp.interpolate:main',
    'ismip7-process-experiment': 'ismip7_interp.experiment:main',
    'ismip7-run-all': 'ismip7_interp.run_all:main',
    'ismip7-inventory': 'ismip7_interp.inventory:main',
}


def module_main(module_path: str):
    """Import ``package.module:main`` from an entry-point specification."""
    from importlib import import_module

    module, _, attribute = module_path.partition(':')
    return getattr(import_module(module), attribute)


@pytest.mark.parametrize('name, target', sorted(ENTRY_POINTS.items()))
def test_every_entry_point_resolves(name, target):
    assert callable(module_main(target))


def test_the_declared_entry_points_are_the_ones_that_exist():
    """A console script that pyproject.toml declares but nothing defines."""
    try:
        declared = {point.name: point.value for point in
                    metadata.distribution('ismip7-interpolation').entry_points
                    if point.group == 'console_scripts'}
    except metadata.PackageNotFoundError:
        pytest.skip('ismip7-interpolation is not installed')
    assert declared == ENTRY_POINTS


@pytest.mark.parametrize('target', sorted(ENTRY_POINTS.values()))
def test_help_works_without_cdo(target, monkeypatch):
    """--help must answer even where CDO is not installed."""
    monkeypatch.setattr('shutil.which', lambda _name: None)
    with pytest.raises(SystemExit) as caught:
        module_main(target)(['--help'])
    assert caught.value.code == 0


@pytest.mark.parametrize('target', sorted(ENTRY_POINTS.values()))
def test_version_reports_the_package_version(target, capsys):
    with pytest.raises(SystemExit) as caught:
        module_main(target)(['--version'])
    assert caught.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_every_command_maps_to_a_module_with_a_main():
    for module in COMMANDS.values():
        assert callable(module_main(f'{module}:main'))


def test_python_m_lists_its_commands():
    result = subprocess.run(
        [sys.executable, '-m', 'ismip7_interp', '--help'],
        capture_output=True, text=True)
    assert result.returncode == 0
    for command in COMMANDS:
        assert command in result.stdout


def test_python_m_rejects_an_unknown_command():
    result = subprocess.run(
        [sys.executable, '-m', 'ismip7_interp', 'regrid-everything'],
        capture_output=True, text=True)
    assert result.returncode == 2
    assert 'unknown command' in result.stderr


def test_python_m_dispatches_to_a_command():
    result = subprocess.run(
        [sys.executable, '-m', 'ismip7_interp', 'inventory', '--help'],
        capture_output=True, text=True)
    assert result.returncode == 0
    assert 'ismip7-inventory' in result.stdout


def test_python_m_with_no_command_is_a_usage_error():
    result = subprocess.run(
        [sys.executable, '-m', 'ismip7_interp'],
        capture_output=True, text=True)
    assert result.returncode == 2


# --- argument helpers ------------------------------------------------------

@pytest.mark.parametrize('text', ['0', '-1', 'fine', '4.5', ''])
def test_positive_int_rejects(text):
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        cli.positive_int(text)


def test_positive_int_accepts():
    assert cli.positive_int('4000') == 4000


@pytest.mark.parametrize('text', ['-1', '101', 'most', ''])
def test_percentage_rejects(text):
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        cli.percentage(text)


@pytest.mark.parametrize('text', ['0', '60', '100'])
def test_percentage_accepts(text):
    assert cli.percentage(text) == int(text)


def test_resolve_experiments_root_uses_the_domain_default(monkeypatch,
                                                          tmp_path):
    from ismip7_interp.archive import DEFAULT_EXPERIMENTS_ROOT

    monkeypatch.setitem(DEFAULT_EXPERIMENTS_ROOT, 'GrIS', tmp_path)
    assert cli.resolve_experiments_root(None, 'GrIS') == tmp_path


def test_resolve_experiments_root_reports_a_missing_directory(tmp_path):
    with pytest.raises(NotADirectoryError, match='--experiments-root'):
        cli.resolve_experiments_root(tmp_path / 'absent', 'GrIS')


def test_run_main_turns_an_expected_error_into_a_status(caplog):
    def work():
        raise FileNotFoundError('no such file')

    assert cli.run_main(work) == 1
    assert 'no such file' in caplog.text


def test_run_main_lets_an_unexpected_error_through():
    """A bug in this package must surface as a traceback, not exit 1."""
    def work():
        raise ZeroDivisionError('a bug')

    with pytest.raises(ZeroDivisionError):
        cli.run_main(work)


# --- CDO's absence ---------------------------------------------------------

def test_require_cdo_explains_how_to_install_it(monkeypatch):
    monkeypatch.setattr('shutil.which', lambda _name: None)
    with pytest.raises(CdoNotFoundError) as caught:
        require_cdo()
    message = str(caught.value)
    assert 'conda-forge' in message
    assert 'PATH' in message


def test_run_cdo_reports_a_missing_cdo_before_running_anything(monkeypatch):
    monkeypatch.setattr('shutil.which', lambda _name: None)
    with pytest.raises(CdoNotFoundError):
        run_cdo(['griddes', 'file.nc'], capture=True)


@pytest.mark.cdo
def test_run_cdo_reports_a_failing_command(tmp_path):
    from ismip7_interp.cdo import CdoError

    with pytest.raises(CdoError, match='exit status'):
        run_cdo(['griddes', str(tmp_path / 'absent.nc')], capture=True)


@pytest.mark.cdo
def test_run_cdo_does_not_leave_diagnostics_on_stdout(capfd, fixture_files,
                                                      tmp_path):
    """CDO writes progress to stdout; nothing may mistake it for data."""
    run_cdo(['-s', 'copy', str(fixture_files['lithk']),
             str(tmp_path / 'copy.nc')])
    assert capfd.readouterr().out == ''
