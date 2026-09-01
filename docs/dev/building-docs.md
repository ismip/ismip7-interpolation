# Building the documentation

These pages are [Sphinx](https://www.sphinx-doc.org/) with
[MyST](https://myst-parser.readthedocs.io/), so the sources are ordinary
Markdown, and are published to
<https://ismip.github.io/ismip7-interpolation/> by GitHub Actions.

## Build them locally

The developer environment from {doc}`source-install` already has Sphinx and its
extensions, so there is nothing else to install:

```bash
conda activate ismip7-interp
sphinx-build -W --keep-going -b html docs docs/_build/html
```

Then open `docs/_build/html/index.html`. `-W` turns warnings into errors, which
is what CI does, so a build that is clean here will not fail there; drop it
while you are iterating if you prefer.

The build needs neither the package nor any of its dependencies — it documents
the command-line interface rather than importing anything, and takes the
version from `pyproject.toml` — so `ci/docs_env.yml` holds Sphinx and its
extensions and nothing else. That matters more here than in most projects:
without it, editing prose would mean installing CDO. That is the environment
CI builds in, and it is worth having locally if you are only editing pages:

```bash
conda env create -f ci/docs_env.yml
conda activate ismip7-interp-docs
sphinx-build -W --keep-going -b html docs docs/_build/html
```

The documentation packages appear in three places — the documentation section
of `ismip7_interp_env.yml`, `ci/docs_env.yml`, and the `docs` extra in
`pyproject.toml` — and adding one means adding it to all three.

## Layout

```
docs/
├── conf.py               Sphinx configuration
├── index.md              landing page
├── getting-started.md    install and first run
├── user/                 for people regridding ISMIP7 output
├── dev/                  for people working on the package
└── _static/              CSS
```

Adding a page means writing the Markdown file and adding it to the `toctree` in
`user/index.md` or `dev/index.md`. A page in neither is a warning, and so a
failed build in CI, which is deliberate: a page nothing links to is a page
nobody reads.

Cross-references between pages use `{doc}` for a whole page —
``{doc}`../user/running` `` — and an ordinary Markdown link with an anchor for
a section within one: `[the weight cache](output.md#the-weight-cache)`.
Anchors exist for headings down to `<h3>`, and are the heading text lowercased
with spaces replaced by hyphens.

## How it is published

`.github/workflows/docs.yml` builds the docs on every push and pull request,
and deploys them to GitHub Pages on pushes to `main`. A pull request therefore
fails if it breaks the docs, but only `main` is ever published.

```{note}
Publishing requires that **Settings → Pages → Build and deployment → Source**
be set to **GitHub Actions** in the repository settings, which needs admin
rights on the repository. Until it is, the build job still runs and still
catches broken docs; the deploy job is what fails.
```
