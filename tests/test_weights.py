"""The remap-weight cache."""

from __future__ import annotations

from pathlib import Path

import pytest

from ismip7_interp.weights import (
    WEIGHTS_DIR_ENV,
    default_weights_dir,
    ensure_weights,
    weight_file_path,
)

from conftest import SOURCE_RES, TARGET_RES


@pytest.mark.parametrize('domain, source, target, method, expected', [
    ('GrIS', 1000, 4000, 'ycon', 'GrIS_01000m_to_04000m_ycon.nc'),
    ('GrIS', 16000, 8000, 'bil', 'GrIS_16000m_to_08000m_bil.nc'),
    ('AIS', 32000, 2000, 'nn', 'AIS_32000m_to_02000m_nn.nc'),
])
def test_weight_file_path(tmp_path, domain, source, target, method, expected):
    assert weight_file_path(tmp_path, domain, source, target,
                            method).name == expected


def test_weight_file_path_distinguishes_direction(tmp_path):
    """Coarsening and refining between the same pair are different weights."""
    down = weight_file_path(tmp_path, 'GrIS', 16000, 8000, 'ycon')
    up = weight_file_path(tmp_path, 'GrIS', 8000, 16000, 'ycon')
    assert down != up


def test_weight_file_path_distinguishes_method(tmp_path):
    paths = {weight_file_path(tmp_path, 'GrIS', 16000, 8000, method)
             for method in ('ycon', 'bil', 'nn')}
    assert len(paths) == 3


def test_default_weights_dir_honors_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv(WEIGHTS_DIR_ENV, str(tmp_path / 'elsewhere'))
    assert default_weights_dir() == tmp_path / 'elsewhere'


def test_default_weights_dir_falls_back_to_a_cache_directory(monkeypatch,
                                                             tmp_path):
    monkeypatch.delenv(WEIGHTS_DIR_ENV, raising=False)
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path))
    assert default_weights_dir() == tmp_path / 'ismip7-interpolation/weights'


def test_default_weights_dir_is_not_inside_the_installation(monkeypatch):
    """The package may be installed read-only; the cache must not be in it."""
    monkeypatch.delenv(WEIGHTS_DIR_ENV, raising=False)
    import ismip7_interp
    package = Path(ismip7_interp.__file__).parent
    assert not default_weights_dir().is_relative_to(package)


def test_ensure_weights_rejects_an_unknown_method(tmp_path):
    with pytest.raises(ValueError, match='unknown remapping method'):
        ensure_weights(tmp_path, 'GrIS', 16000, 8000, 'quadratic')


def test_ensure_weights_returns_a_cached_file_without_running_cdo(
        tmp_path, fake_cdo):
    weights = weight_file_path(tmp_path, 'GrIS', 16000, 8000, 'ycon')
    weights.parent.mkdir(parents=True, exist_ok=True)
    weights.write_bytes(b'cached')
    assert ensure_weights(tmp_path, 'GrIS', 16000, 8000, 'ycon') == weights
    assert fake_cdo == []
    assert weights.read_bytes() == b'cached'


def test_ensure_weights_generates_from_the_grids_alone(tmp_path, fake_cdo):
    """No archive file is involved: the weights depend only on geometry."""
    ensure_weights(tmp_path, 'GrIS', 16000, 8000, 'ycon')
    assert len(fake_cdo) == 2
    template, generate = fake_cdo
    assert template[:2] == ['-f', 'nc']
    assert template[2].startswith('const,1,')
    assert generate[0].startswith('genycon,')


@pytest.mark.parametrize('method, operator', [
    ('ycon', 'genycon'),
    ('bil', 'genbil'),
    ('nn', 'gennn'),
])
def test_ensure_weights_uses_the_matching_generator(tmp_path, fake_cdo,
                                                    method, operator):
    ensure_weights(tmp_path, 'GrIS', 16000, 8000, method)
    assert fake_cdo[1][0].startswith(f'{operator},')


def test_ensure_weights_leaves_no_scratch_directory(tmp_path, fake_cdo):
    ensure_weights(tmp_path, 'GrIS', 16000, 8000, 'ycon')
    assert list(tmp_path.glob('.gen_*')) == []


def test_ensure_weights_cleans_up_when_cdo_fails(tmp_path, monkeypatch):
    """A crash part-way must leave no scratch directory and no weight file."""
    from ismip7_interp.cdo import CdoError

    def fail(args, capture=False, verbose=False):
        raise CdoError('boom')

    monkeypatch.setattr('ismip7_interp.cdo.run_cdo', fail)
    with pytest.raises(CdoError):
        ensure_weights(tmp_path, 'GrIS', 16000, 8000, 'ycon')
    assert not weight_file_path(tmp_path, 'GrIS', 16000, 8000,
                                'ycon').exists()
    assert list(tmp_path.glob('.gen_*')) == []


def test_ensure_weights_reports_an_unknown_resolution(tmp_path, fake_cdo):
    from ismip7_interp.grids import GridError

    with pytest.raises(GridError):
        ensure_weights(tmp_path, 'GrIS', 3000, 8000, 'ycon')


@pytest.mark.cdo
def test_ensure_weights_really_generates_usable_weights(weights_dir):
    """The whole point, exercised against real CDO."""
    weights = ensure_weights(weights_dir, 'GrIS', SOURCE_RES, TARGET_RES,
                             'ycon')
    assert weights.is_file()
    assert weights.stat().st_size > 0


@pytest.mark.cdo
def test_ensure_weights_reuses_what_it_generated(weights_dir):
    first = ensure_weights(weights_dir, 'GrIS', SOURCE_RES, TARGET_RES, 'ycon')
    stamp = first.stat().st_mtime_ns
    second = ensure_weights(weights_dir, 'GrIS', SOURCE_RES, TARGET_RES,
                            'ycon')
    assert second == first
    assert second.stat().st_mtime_ns == stamp
