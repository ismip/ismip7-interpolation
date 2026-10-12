---
name: user-docs
description: Write or revise anything a person regridding an archive reads. That is docs/user/, docs/getting-started.md, docs/index.md, README.md, the --help strings and the log and error messages. Use when documenting a command, an option or a remapping choice, or wording a message. Not for docs/dev/.
---

# User documentation

The reader has an archive to regrid and a terminal in front of them:
mostly a member of the ISMIP7 team regridding the whole ensemble on
NIRD, sometimes a modeler with their own output. They do not read the
code, and English may not be their first language.

- Say what to do, then show what they will see: the command, then the
  output or log lines it produces. The natural mistake, shown with the
  output it gives, teaches more than a rule against it.
- Show a path or a file name as it is, annotated, not as a template with
  field names. A template is how a modeler came to pass the wrong
  directory (ismip/ismip7-scalar-processing#10).
- Backticks are for what the reader types: commands, options and their
  values. Paths, file names, variable names and CDO operators go in plain
  text.
- Say what the tools do, not why they were designed that way. Cut any
  sentence whose job is to justify the one before it.
- Each thing is explained on one page. Other pages link to it with
  `{doc}` rather than explaining it again.
- The getting-started page goes in the order the reader meets things:
  install, lay out the archive, look at it, regrid it, read the output.
  The user guide is a reference, and the reader jumps to the page they
  need.
- A `--help` string is a lowercase phrase, as argparse's own are. It says
  what the option takes, gives an example value where the form is not
  obvious, and ends with the default in parentheses.
- An error names what is wrong and what was expected, then stops. At
  most one thing to check.

## Calibration

#2 rewrote these pages to this standard. Outside code blocks, the README
and the user pages went from 3100 words to 2200, from 168 backticked
spans to 70, and from 20 words per sentence to 16, and they gained nine
code blocks, most of them directory trees and real output. Hold those.

## Enough

The natural mistake, with what it produces (docs/getting-started.md):

> `--target-res` is in meters. Asking for a resolution ISMIP7 does not
> have lists the ones it does:
>
> ```
> no ISMIP7 grid for domain=GrIS resolution=4m (known GrIS resolutions: 1000, 2000, 4000, 5000, 8000, 16000)
> ```

A help string, after #2:

> only these variables, by the name that starts each filename, e.g.
> lithk,acabf (default: every variable found)

A feature in one line, after #2:

> Computes remap weights once per grid pair and reuses them across the
> archive.

## Too much

The same feature before #2, with its justification attached:

> **Caches remap weights** per grid pair and method, so the expensive
> part of conservative remapping happens once for a whole archive rather
> than once per file.

The same help string before #2, in the code's vocabulary rather than the
reader's:

> restrict processing to these ISMIP7 variables, matched against the
> first "_"-separated token of each filename; the default is every
> variable found

## Described, not shown

The output layout before #2, as a template the reader has to fill in:

> ```
> OUTPUT_ROOT/GrIS_04000m/<group>/<model>/<experiment-set>/<experiment>/*.nc
> OUTPUT_ROOT/GrIS_04000m/logs/
> ```

After, as a tree the reader can hold beside their own:

> ```
> output/GrIS_04000m/
> ├── NORCE/CISM3/CORE/C001/lithk_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_historical_C001_1850-2014.nc
> ├── NORCE/CISM3/CORE/C007/...
> ├── AWI/PISM/CORE/C007/...
> └── logs/
> ```
