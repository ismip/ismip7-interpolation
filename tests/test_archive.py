"""Finding experiments in an archive, and the shapes real archives come in."""

from __future__ import annotations

from pathlib import Path

import pytest

from ismip7_interp.archive import (
    DEFAULT_EXPERIMENTS_ROOT,
    ExperimentSet,
    experiment_rel_path,
    experiment_sets,
    find_experiments,
    has_nc_files,
    nc_files,
    parse_variable_filter,
    variable_wanted,
)
from ismip7_interp.grids import DOMAINS

NC = ['lithk_GrIS_x.nc']


def test_every_domain_has_a_default_archive_root():
    assert set(DEFAULT_EXPERIMENTS_ROOT) == set(DOMAINS)


def test_configured_experiment_sets():
    sets = experiment_sets()
    assert sets
    core = next(item for item in sets if item.name == 'CORE')
    assert core.prefix == 'C'


@pytest.mark.parametrize('name, expected', [
    ('C001', True),
    ('C011', True),
    ('C000', False),
    ('C012', False),
    # Not three digits.
    ('C01', False),
    ('C0011', False),
    # Right numbers, wrong prefix.
    ('E001', False),
    # Trailing text after a valid number.
    ('C001a', False),
])
def test_experiment_set_matches(name, expected):
    core = ExperimentSet('CORE', 'C', 1, 11)
    assert core.matches(name) is expected


def test_experiment_set_reads_a_leading_zero_as_decimal():
    """C008 and C009 are not octal, however they look."""
    core = ExperimentSet('CORE', 'C', 1, 11)
    assert core.matches('C008')
    assert core.matches('C009')


def test_find_experiments_accepts_a_well_formed_experiment(
        tmp_path, make_archive):
    make_archive(tmp_path, {'GroupA/ModelA/CORE/C001': NC})
    assert find_experiments(tmp_path) == [
        tmp_path / 'GroupA/ModelA/CORE/C001']


@pytest.mark.parametrize('relative', [
    # Renamed or deprecated experiment-set directories.
    'GroupB/ModelB/old_CORE/C001',
    'GroupC/ModelC/CORE_old/C001',
    'GroupD/ModelD/CESM2-WACCM_CORE/C001',
    # A live-looking CORE nested inside a dead one.
    'GroupE/ModelE/old_CORE/CORE/C001',
    # An experiment number outside the configured range.
    'GroupF/ModelF/CORE/C012',
    # Not an experiment name at all.
    'GroupG/ModelG/CORE/scratch',
])
def test_find_experiments_rejects(tmp_path, make_archive, relative):
    make_archive(tmp_path, {relative: NC})
    assert find_experiments(tmp_path) == []


def test_find_experiments_ignores_a_directory_with_no_nc_files_of_its_own(
        tmp_path, make_archive):
    """Mirrors the archive's stray trees: right name, data further down."""
    make_archive(tmp_path, {'G/M/CORE/C001/Users/someone': ['leftover.nc']})
    assert find_experiments(tmp_path) == []


def test_find_experiments_is_case_insensitive_about_deprecated_markers(
        tmp_path, make_archive):
    make_archive(tmp_path, {'G/M/OLD_core/CORE/C001': NC})
    assert find_experiments(tmp_path) == []


def test_find_experiments_returns_each_directory_once(tmp_path, make_archive):
    """A nested set directory must not yield the same experiment twice.

    The inventory counts what this returns, so a duplicate would be counted
    and its bytes added twice.
    """
    make_archive(tmp_path, {'G/M/CORE/C001': NC, 'G/M/CORE/CORE/C002': NC})
    found = find_experiments(tmp_path)
    assert len(found) == len(set(found))


def test_find_experiments_is_sorted(tmp_path, make_archive):
    make_archive(tmp_path, {
        'Z/M/CORE/C003': NC, 'A/M/CORE/C001': NC, 'M/M/CORE/C002': NC})
    assert find_experiments(tmp_path) == sorted(find_experiments(tmp_path))


def test_find_experiments_finds_several_across_groups(tmp_path, make_archive):
    make_archive(tmp_path, {
        'GroupA/ModelA/CORE/C001': NC,
        'GroupA/ModelA/CORE/C002': NC,
        'GroupB/ModelB/CORE/C001': NC,
    })
    assert len(find_experiments(tmp_path)) == 3


def test_find_experiments_on_an_empty_root(tmp_path):
    assert find_experiments(tmp_path) == []


def test_nc_files_only_looks_directly_inside(tmp_path, make_archive):
    make_archive(tmp_path, {'exp': ['b.nc', 'a.nc', 'notes.txt'],
                            'exp/deeper': ['c.nc']})
    found = nc_files(tmp_path / 'exp')
    assert [path.name for path in found] == ['a.nc', 'b.nc']


def test_nc_files_ignores_a_directory_named_like_one(tmp_path):
    (tmp_path / 'exp' / 'trap.nc').mkdir(parents=True)
    assert nc_files(tmp_path / 'exp') == []
    assert not has_nc_files(tmp_path / 'exp')


def test_nc_files_limit_stops_early(tmp_path, make_archive):
    make_archive(tmp_path, {'exp': ['a.nc', 'b.nc', 'c.nc']})
    assert len(nc_files(tmp_path / 'exp', limit=1)) == 1


@pytest.mark.parametrize('text, expected', [
    (None, None),
    ('', None),
    ('   ', None),
    ('lithk', frozenset({'lithk'})),
    ('lithk,acabf', frozenset({'lithk', 'acabf'})),
    # Whitespace around names, which is how anyone would type it by hand.
    ('lithk, acabf', frozenset({'lithk', 'acabf'})),
    (' lithk , acabf ', frozenset({'lithk', 'acabf'})),
    # Stray separators rather than an error.
    ('lithk,,acabf,', frozenset({'lithk', 'acabf'})),
])
def test_parse_variable_filter(text, expected):
    assert parse_variable_filter(text) == expected


def test_variable_wanted():
    assert variable_wanted('lithk', None)
    assert variable_wanted('lithk', parse_variable_filter('lithk,acabf'))
    assert not variable_wanted('orog', parse_variable_filter('lithk,acabf'))
    # A filter written with spaces means what it looks like it means.
    assert variable_wanted('acabf', parse_variable_filter('lithk, acabf'))


def test_experiment_rel_path_under_the_root(tmp_path):
    experiment = tmp_path / 'GroupA/ModelA/CORE/C001'
    experiment.mkdir(parents=True)
    assert experiment_rel_path(experiment, tmp_path) == Path(
        'GroupA/ModelA/CORE/C001')


def test_experiment_rel_path_keeps_the_group_when_outside_the_root(
        tmp_path):
    """The fallback must keep group/model/set/experiment, not drop the group.

    Two groups can hold the same model, set and experiment number, so a
    fallback of only three components would write both into one directory.
    """
    experiment = tmp_path / 'GroupA/ModelA/CORE/C001'
    experiment.mkdir(parents=True)
    elsewhere = tmp_path / 'unrelated'
    elsewhere.mkdir()
    assert experiment_rel_path(experiment, elsewhere) == Path(
        'GroupA/ModelA/CORE/C001')


def test_experiment_rel_path_with_no_root_given(tmp_path):
    experiment = tmp_path / 'GroupA/ModelA/CORE/C001'
    experiment.mkdir(parents=True)
    assert experiment_rel_path(experiment, None) == Path(
        'GroupA/ModelA/CORE/C001')


def test_experiment_rel_paths_of_two_groups_do_not_collide(tmp_path):
    """The whole point of keeping four components rather than three."""
    first = tmp_path / 'GroupA/ModelA/CORE/C001'
    second = tmp_path / 'GroupB/ModelA/CORE/C001'
    for path in (first, second):
        path.mkdir(parents=True)
    elsewhere = tmp_path / 'unrelated'
    elsewhere.mkdir()
    assert (experiment_rel_path(first, elsewhere)
            != experiment_rel_path(second, elsewhere))
