"""Entry point for ``python -m ismip7_interp``.

Each command also installs as a console script of its own; this dispatcher
exists so that the package can be driven without them, which is what makes it
runnable straight out of a source checkout.
"""

from __future__ import annotations

import sys

COMMANDS = {
    'interpolate': 'ismip7_interp.interpolate',
    'process-experiment': 'ismip7_interp.experiment',
    'run-all': 'ismip7_interp.run_all',
    'inventory': 'ismip7_interp.inventory',
}

USAGE = (
    'usage: python -m ismip7_interp {' + ','.join(COMMANDS) + '} ...\n\n'
    'Run a command with --help for its own options.  Each is also installed '
    'as a console script:\n'
    '  interpolate         ismip7-interpolate\n'
    '  process-experiment  ismip7-process-experiment\n'
    '  run-all             ismip7-run-all\n'
    '  inventory           ismip7-inventory\n')


def main(argv: list[str] | None = None) -> int:
    """Dispatch to one command's ``main``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ('-h', '--help'):
        print(USAGE, end='')
        return 0 if argv else 2
    command = argv[0]
    if command not in COMMANDS:
        print(f'unknown command {command!r}\n\n{USAGE}', end='',
              file=sys.stderr)
        return 2
    from importlib import import_module
    return import_module(COMMANDS[command]).main(argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
