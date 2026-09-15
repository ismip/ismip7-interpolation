# How a remapping is chosen

The variable name at the start of a filename, lithk in
lithk_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_ssp585_C007_2015-2300.nc,
decides everything on this page.

## The decision, in order

1. **Does the variable have a spatial grid?** The domain-integrated time
   series (lim, limnsw, iareagr, iareafl and the tend* fluxes) have nothing
   to remap and are placed unchanged; see {doc}`output`. This comes from the
   ISMIP7 data request, and `--method` cannot change it.

2. **Which algorithm?**

   | Remapping | CDO operator | Variables |
   |---|---|---|
   | conservative (default) | remapycon | everything else |
   | bilinear | remapbil | the velocity components xvelsurf, yvelsurf, zvelsurf, xvelbase, yvelbase, zvelbase, xvelmean, yvelmean |
   | nearest-neighbor | remapnn | none yet |

3. **Is the file already at the target resolution?** Then it is placed
   unchanged too.

`--method` overrides step 2 for a variable with a spatial grid.

## Why conservative, and why the velocities differ

Conservative remapping preserves the integral of a field over the domain, so
the total ice mass or total flux does not change because the grid did. A
single component of a vector has no such integral to preserve, so the
velocity components are interpolated bilinearly instead.

Nearest-neighbor is meant for categorical or mask-like fields, where
averaging would blur a sharp boundary into fractions. The area-fraction masks
sftgif, sftgrf and sftflf are candidates, but none has been confirmed against
real data yet, so they are remapped conservatively for now. For a fraction
field that is defensible: a cell's fractional coverage is an area average.

## Missing values

Before remapping, missing source cells are filled with 0. That makes every
file's missing-value mask the same, which is what lets one set of remap
weights be computed per grid pair and reused across the archive; see
{doc}`output`.

Filling with 0 is right where 0 means something outside the ice sheet: ice
thickness is 0 where there is no ice. It is wrong for velocity, where a 0 m/s
outside the ice sheet would be averaged into real velocities at the edge. The
velocity components therefore keep their real mask and do not use the weight
cache, unless a file turns out to have no missing values at all.

## Changing any of this

The configuration is three files in ismip7_interp/data/config, one variable
name per line, with `#` comments:

| File | Variables |
|---|---|
| bilinear_variables.txt | remapped bilinearly |
| nearest_variables.txt | remapped nearest-neighbor |
| mask_missing_variables.txt | keep their real missing-value mask |

The test suite checks every name against the ISMIP7 data request, so a typo
cannot silently never match. Adding a variable changes what users get, so it
wants a release; see {doc}`../dev/releasing`.
