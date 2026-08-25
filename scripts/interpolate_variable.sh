#!/usr/bin/env bash
# Regrid a single ISMIP7 NetCDF file onto a target ISMIP7 grid.
#
# Usage:
#   interpolate_variable.sh --domain GrIS|AIS --target-res METERS \
#       [--method ycon|bil|nn|auto] [--on-unchanged symlink|copy|skip] \
#       IN.nc OUT.nc
#
# A file is left "unchanged" (not regridded) in two cases: it's a
# scalar time-series variable (see config/scalar_variables.txt, no
# spatial grid to remap), or it's already at the target resolution.
# --on-unchanged controls how it's placed at OUT.nc in either case:
#   symlink (default) -- OUT.nc is a symlink to IN.nc (saves disk,
#     avoids copying potentially large files that aren't changing)
#   copy   -- OUT.nc is a real copy of IN.nc
#   skip   -- nothing is written to OUT.nc at all
#
# --method auto (default) picks conservative (remapycon) unless the
# variable is in config/bilinear_variables.txt (bilinear, remapbil)
# or config/nearest_variables.txt (nearest-neighbor, remapnn).
#
# Missing source cells are filled with 0 (cdo setmisstoc,0) before
# remapping unless the variable is listed in
# config/mask_missing_variables.txt, in which case its actual
# missing-value pattern is preserved -- UNLESS the file happens to
# have no missing values at all, in which case there's nothing to
# preserve and the shared weights below still apply. Filling makes
# the source mask uniform, which is what lets remap weights be
# precomputed once per (domain, source_res, target_res, method) and
# reused from weights/ instead of cdo recomputing them per file.

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

domain=""
target_res=""
method="auto"
on_unchanged="symlink"
positional=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain) domain="$2"; shift 2 ;;
        --target-res) target_res="$2"; shift 2 ;;
        --method) method="$2"; shift 2 ;;
        --on-unchanged) on_unchanged="$2"; shift 2 ;;
        -h|--help) grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) positional+=("$1"); shift ;;
    esac
done

[[ ${#positional[@]} -eq 2 ]] || die "usage: $(basename "$0") --domain GrIS|AIS --target-res METERS [--method ycon|bil|auto] [--on-unchanged symlink|copy|skip] IN.nc OUT.nc"
in_file="${positional[0]}"
out_file="${positional[1]}"

[[ -n "${domain}" ]] || die "--domain is required (GrIS or AIS)"
[[ "${domain}" == "GrIS" || "${domain}" == "AIS" ]] || die "--domain must be GrIS or AIS, got '${domain}'"
[[ -n "${target_res}" ]] || die "--target-res is required (meters)"
[[ -f "${in_file}" ]] || die "input file not found: ${in_file}"
[[ "${method}" == "auto" || "${method}" == "ycon" || "${method}" == "bil" || "${method}" == "nn" ]] || die "--method must be ycon, bil, nn or auto"
[[ "${on_unchanged}" == "symlink" || "${on_unchanged}" == "copy" || "${on_unchanged}" == "skip" ]] || die "--on-unchanged must be symlink, copy or skip"

mkdir -p "$(dirname "${out_file}")"

# bash 3.2 (macOS default) has no ${var^^}; keep this portable.
on_unchanged_upper="$(tr '[:lower:]' '[:upper:]' <<< "${on_unchanged}")"

var="$(var_from_filename "${in_file}")"
resolved_method="${method}"
[[ "${method}" == "auto" ]] && resolved_method="$(interp_method "${var}")"

if [[ "${resolved_method}" == "copy" ]]; then
    log "${on_unchanged_upper} ${var}: scalar/non-gridded variable, no regridding applicable"
    place_unchanged "${in_file}" "${out_file}" "${on_unchanged}"
    exit 0
fi

target_gdf="$(gdf_path "${domain}" "${target_res}")"
source_res="$(detect_source_res "${domain}" "${in_file}")"
source_gdf="$(gdf_path "${domain}" "${source_res}")"

if [[ "${source_res}" -eq "${target_res}" ]]; then
    log "${on_unchanged_upper} ${var}: already at target resolution (${target_res}m)"
    place_unchanged "${in_file}" "${out_file}" "${on_unchanged}"
    exit 0
fi

# --method override forces the algorithm even for a variable that
# would otherwise resolve to "copy" only via the scalar-variable
# check above, which already returned by this point -- so here
# resolved_method is always ycon, bil or nn.
cdo_op="remapycon"
case "${resolved_method}" in
    bil) cdo_op="remapbil" ;;
    nn)  cdo_op="remapnn" ;;
esac

use_cache=0
apply_setmisstoc=0
if use_setmisstoc "${var}"; then
    use_cache=1
    apply_setmisstoc=1
elif ! has_missing_values "${in_file}"; then
    use_cache=1
fi

if [[ "${use_cache}" -eq 1 ]]; then
    weight_file="$(ensure_weights "${domain}" "${source_res}" "${target_res}" "${resolved_method}")"
    log "REGRID ${var}: ${source_res}m -> ${target_res}m via ${cdo_op} (cached weights)"
    if [[ "${apply_setmisstoc}" -eq 1 ]]; then
        cdo -v remap,"${target_gdf}","${weight_file}" -setmisstoc,0 -setgrid,"${source_gdf}" "${in_file}" "${out_file}"
    else
        cdo -v remap,"${target_gdf}","${weight_file}" -setgrid,"${source_gdf}" "${in_file}" "${out_file}"
    fi
else
    log "REGRID ${var}: ${source_res}m -> ${target_res}m via ${cdo_op} (missing-value mask preserved, weights not cached)"
    cdo -v "${cdo_op},${target_gdf}" -setgrid,"${source_gdf}" "${in_file}" "${out_file}"
fi
