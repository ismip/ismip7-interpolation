#!/usr/bin/env bash
# Generate small synthetic ISMIP7-style NetCDF fixtures for the smoke
# tests. Regenerated fresh on every test run (not checked into git);
# safe to re-run any time.
#
# Spatial fixtures use cdo's own `random` grid generator on the
# smallest checked-in GDF (GrIS 16km, 106x181 points) so tests stay
# fast. The scalar fixture is built with `ncgen` from a literal CDL
# description, since it needs no x,y grid at all (matching the real
# archive's "t"-only variables like `lim`), which cdo has no generator
# for.

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${REPO_ROOT}/tests/fixtures/data"
mkdir -p "${OUT_DIR}"

SRC_GDF="${REPO_ROOT}/gdfs/gdf_ISMIP7_GrIS_16000m.txt"
SUFFIX="GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc"

make_spatial() {
    local var="$1"
    cdo -s -f nc4 chname,random,"${var}" -random,"${SRC_GDF}" "${OUT_DIR}/${var}_${SUFFIX}"
}

# Same as make_spatial, but with a genuine (partial, not total) block
# of missing values -- for exercising the mask-preserved path of a
# config/mask_missing_variables.txt variable, where the actual
# missing-value pattern must not be touched by setmisstoc,0.
# cdo's `random` operator draws from [0,1), so 0.4-0.6 is a safe
# middle slice to blank out regardless of exact distribution details.
make_spatial_missing() {
    local var="$1"
    cdo -s -f nc4 chname,random,"${var}" -setrtomiss,0.4,0.6 -random,"${SRC_GDF}" "${OUT_DIR}/${var}_${SUFFIX}"
}

# ST state variable -> should resolve to conservative (remapycon)
make_spatial lithk
# FL flux variable -> should also resolve to conservative
make_spatial acabf
# in the bilinear exception list, no missing values -> should still
# resolve to remapbil AND be eligible for cached weights (nothing to
# mask-preserve)
make_spatial xvelsurf
# also in the bilinear/mask-missing exception list, but WITH real
# missing values this time -> must preserve its mask, not use cached
# weights
make_spatial_missing yvelsurf

# Scalar ("t" only, no x,y grid) -> should be copied through unchanged,
# never handed to cdo remap/setgrid.
cdl_file="$(mktemp)"
cat > "${cdl_file}" <<'EOF'
netcdf lim {
dimensions:
    time = UNLIMITED ;
variables:
    double time(time) ;
        time:units = "days since 1850-01-01" ;
        time:calendar = "standard" ;
    float lim(time) ;
        lim:_FillValue = -9999.f ;
data:
 time = 60225, 60590 ;
 lim = 1.0e15, 1.01e15 ;
}
EOF
ncgen -o "${OUT_DIR}/lim_${SUFFIX}" "${cdl_file}"
rm -f "${cdl_file}"

echo "fixtures written to ${OUT_DIR}" >&2
