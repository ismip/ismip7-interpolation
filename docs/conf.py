# Configuration file for the Sphinx documentation builder.
from __future__ import annotations

import tomllib
from datetime import datetime
from pathlib import Path

_docs_dir = Path(__file__).parent
_repo_root = _docs_dir.parent

# -- Project information -----------------------------------------------------

project = 'ISMIP7 Interpolation'
author = 'ISMIP contributors'
copyright = f'{datetime.now().year}, {author}'

# Read the version from pyproject.toml rather than from the installed package,
# so that the docs can be built from a checkout without installing anything --
# and, in particular, without installing CDO.
with open(_repo_root / 'pyproject.toml', 'rb') as _pyproject:
    release = tomllib.load(_pyproject)['project']['version']
version = release

# -- General configuration ---------------------------------------------------

extensions = [
    'myst_parser',
    'sphinx_copybutton',
    'sphinx_design',
]

myst_enable_extensions = [
    'colon_fence',
    'deflist',
    'substitution',
]

# Give every heading down to <h3> an anchor, so that one page can link to a
# section of another page and not merely to its top.
myst_heading_anchors = 3

root_doc = 'index'
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------

html_theme = 'furo'
html_title = f'{project} {release}'
html_static_path = ['_static']
html_css_files = ['custom.css']
html_theme_options = {
    'source_repository': 'https://github.com/ismip/ismip7-interpolation/',
    'source_branch': 'main',
    'source_directory': 'docs/',
}
