# How a remapping is chosen

Every file's variable is read from its filename — the first `_`-separated
token — and that name decides everything on this page.

## The decision, in order

1. **Does the variable have a spatial grid?** Variables whose `Dim` in the
   ISMIP7 data request has no `x` — `lim`, `limnsw`, `iareagr`, `iareafl` and
   the `tend*` fluxes — are domain-integrated time series. There is nothing to
   remap, so they are placed unchanged (see {doc}`output`). This is decided
   from the data request, not from `--method`: asking for an algorithm cannot
   make a time series regriddable, and trying would only hand CDO a file it
   must reject.

2. **Is it configured for a particular algorithm?** Otherwise:

   | Configured as | CDO operator | Applies to |
   |---|---|---|
   | bilinear | `remapbil` | the vector velocity components |
   | nearest-neighbour | `remapnn` | nothing yet — see below |
   | conservative (default) | `remapycon` | everything else |

3. **Is the file already at the target resolution?** Then it is placed
   unchanged too, whatever the algorithm would have been.

`--method` overrides step 2 for a spatial variable. It does not override
step 1 or step 3.

## Why conservative by default

Conservative (area-weighted) remapping preserves the integral of a field over
the domain, which is what you want for a state field such as ice thickness or
a mass flux such as surface mass balance: the total ice mass or the total flux
should not change because the grid did.

## Why the velocity components are different

Conservative remapping of an *individual vector component* is not physically
meaningful the way it is for a scalar. `xvelsurf`, `yvelsurf`, `zvelsurf` and
their `base`/`mean` counterparts are therefore remapped bilinearly, which
interpolates rather than integrates.

The list is in `ismip7_interp/data/config/bilinear_variables.txt`, one name
per line, with the reasoning in the file's own comments.

## Nearest-neighbour

`remapnn` is the right choice for categorical or mask-like fields, where
averaging would blur a sharp boundary into fractional values instead of
picking one class per target cell. The candidates are the area-fraction masks
— `sftgif`, `sftgrf`, `sftflf`.

`ismip7_interp/data/config/nearest_variables.txt` is **empty today**: no
variable has been confirmed against real data yet, and the file is where one
goes once it has been. Until then those masks are remapped conservatively,
which for a fraction field is defensible — a cell's fractional coverage is
genuinely an area average.

## Missing values, and why they matter for speed

Before remapping, missing source cells are filled with 0 (`cdo setmisstoc,0`).
That is not cosmetic: it makes the source field's missing-value mask uniform
across every timestep and every file, which is precisely what lets one set of
remap weights be computed per grid pair and reused (see {doc}`output`).
Without it, CDO recomputes weights whenever the mask differs — which is
per file, and often per timestep.

Filling is right where 0 is a physically meaningful value outside the ice
sheet: ice thickness is legitimately 0 where there is no ice. It is wrong
where it is not — an ice velocity of 0 m/s outside the ice sheet is not a
measurement, and averaging it into neighbouring cells drags real velocities
towards zero.

`ismip7_interp/data/config/mask_missing_variables.txt` lists the variables
that keep their real missing-value pattern instead. Such a file does not use
the weight cache — its mask is its own — **unless it turns out to have no
missing values at all**, in which case there is no mask to preserve and the
shared weights are the right ones. That check reads the data, so it is done
only for the variables on this list.

## Changing any of this

The three files in `ismip7_interp/data/config/` are the whole of the
configuration:

`bilinear_variables.txt`
: variables remapped with `remapbil`

`nearest_variables.txt`
: variables remapped with `remapnn`

`mask_missing_variables.txt`
: variables whose missing-value mask must be preserved

One name per line; `#` comments and blank lines are ignored. A name that is
not in the ISMIP7 data request is a typo that would silently never match, so
the test suite checks every configured name against the request.

Adding a variable to one of these changes what users get, so it wants a
release — see {doc}`../dev/releasing`.
