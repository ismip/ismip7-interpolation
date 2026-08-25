#!/usr/bin/env bash
# Scan an ISMIP7 experiment archive and report, per file and per
# experiment: actual file size, a *predicted* post-regrid size at a
# target resolution, and mandatory-variable completeness against
# config/ISMIP7_variable_request.csv.
#
# This only reads metadata (file size via stat, grid dims via
# `ncdump -h`) -- it never opens or regrids the data itself, so it's
# cheap and safe to run across the whole archive. Grid dims come from
# `ncdump -h`, not `cdo griddes` like the actual regrid scripts use --
# ncdump reads only the declared header (not file content), which
# measured ~200x faster on a real 1.2GB experiment file and doesn't
# require cdo's stricter (CF time-first-dimension) assumptions. A file
# ncdump can read but cdo's remap engine can't would still fail during
# actual regridding -- this scan can't and doesn't predict that.
#
# Usage:
#   inventory_archive.sh --domain GrIS|AIS --target-res METERS \
#       [--experiments-root ROOT] [--output DIR] \
#       [--variables VAR1,VAR2,...]
#
# --variables restricts the scan to the given comma-separated ISMIP7
# variable names (matched via var_from_filename, same as
# process_experiment.sh), skipping every other file's ncdump call
# entirely (not just filtering the report) -- a real speedup, not
# just a smaller files.csv. Mandatory-completeness in experiments.csv
# is scoped to match: only requested variables that are also
# mandatory count towards n_mandatory_expected/missing_mandatory, so
# a filtered run doesn't report the untouched mandatory variables as
# "missing".
#
# Writes DIR/files.csv (one row per .nc file), DIR/experiments.csv
# (one row per experiment, including a "regrid_status" column), and
# DIR/summary.txt (aggregate counts across the whole scan). DIR
# defaults to <repo>/output/inventory_<domain> (e.g.
# output/inventory_GrIS) so a GrIS scan and an AIS scan never collide
# when --output isn't given.
#
# regrid_status per experiment is one of:
#   already_at_target -- every spatial file already matches --target-res
#   needs_regrid       -- at least one spatial file is at a different,
#                         recognized resolution
#   unknown_grid       -- at least one spatial file's dims don't match
#                         any known GDF for --domain
#   no_spatial_data    -- no file could be read as a spatial grid at
#                         all (everything unreadable and/or scalar)
#
# Predicted size is a rough estimate only: actual_bytes scaled by the
# ratio of target grid points to source grid points. It ignores
# header/compression overhead and per-variable dtype differences, so
# treat it as a sanity-check ballpark, not an exact prediction.
# Scalar (non-gridded) variables are always copied unchanged, so
# their predicted size equals their actual size.

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

domain=""
target_res=""
experiments_root=""
output_dir=""
variables_filter=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain) domain="$2"; shift 2 ;;
        --target-res) target_res="$2"; shift 2 ;;
        --experiments-root) experiments_root="$2"; shift 2 ;;
        --output) output_dir="$2"; shift 2 ;;
        --variables) variables_filter="$2"; shift 2 ;;
        -h|--help) grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) die "unrecognized argument: $1" ;;
    esac
done

[[ -n "${domain}" ]] || die "--domain is required (GrIS or AIS)"
[[ -n "${target_res}" ]] || die "--target-res is required (meters)"
output_dir="${output_dir:-${REPO_ROOT}/output/inventory_${domain}}"

if [[ -z "${experiments_root}" ]]; then
    case "${domain}" in
        GrIS) experiments_root="/nird/datalake/NS5011K/ISMIP/ISMIP7/GrIS/ISMIP7_output/ISMIP7_submissions/GrIS" ;;
        AIS)  experiments_root="/nird/datalake/NS5011K/ISMIP/ISMIP7/AIS/ISMIP7_output/ISMIP7_submissions/AIS" ;;
    esac
fi
[[ -d "${experiments_root}" ]] || die "--experiments-root not found: ${experiments_root}"

mkdir -p "${output_dir}"
files_csv="${output_dir}/files.csv"
experiments_csv="${output_dir}/experiments.csv"
summary_txt="${output_dir}/summary.txt"

target_gdf="$(gdf_path "${domain}" "${target_res}")"
read -r target_x target_y < <(gdf_dims "${target_gdf}")
target_points=$(( target_x * target_y ))

mandatory_list="$(mandatory_variables | sort -u)"
if [[ -n "${variables_filter}" ]]; then
    # A `while read` loop's own exit status is that of its final,
    # EOF-failing `read` -- not the loop body's success -- so without
    # `|| true` this command substitution "fails" under set -e even
    # though filtering worked correctly, killing the script silently.
    mandatory_list="$(while IFS= read -r v; do
        variable_wanted "${v}" "${variables_filter}" && echo "${v}"
    done <<< "${mandatory_list}")" || true
fi
n_mand_expected="$(grep -c . <<< "${mandatory_list}" || true)"

echo "experiment,variable,mandatory,kind,source_res_m,actual_bytes,predicted_target_bytes" > "${files_csv}"
echo "experiment,n_files,n_mandatory_expected,n_mandatory_present,missing_mandatory,total_actual_bytes,total_predicted_bytes,regrid_status" > "${experiments_csv}"

n_exp=0
n_already=0
n_needs_regrid=0
n_unknown_grid=0
n_no_spatial=0
while IFS= read -r exp_dir; do
    n_exp=$((n_exp + 1))
    log "[${n_exp}] scanning ${exp_dir}"

    present_vars=""
    n_files=0
    total_actual=0
    total_predicted=0
    n_spatial_matched_offtarget=0
    n_spatial_matched_ontarget=0
    n_spatial_unknown=0

    while IFS= read -r -d '' nc_file; do
        var="$(var_from_filename "${nc_file}")"
        variable_wanted "${var}" "${variables_filter}" || continue
        n_files=$((n_files + 1))
        present_vars="${present_vars} ${var}"
        actual_bytes="$(file_size "${nc_file}")"

        is_mandatory="no"
        list_contains "${var}" <(echo "${mandatory_list}") && is_mandatory="yes"

        # nc_dims_fast dies loudly if ncdump can't even open the file
        # -- guarded here so one bad file doesn't abort the whole scan.
        if ! dims="$(nc_dims_fast "${nc_file}" 2>/dev/null)"; then
            kind="unreadable"
            source_res=""
            predicted_bytes="NA"
        elif [[ -z "${dims// /}" ]]; then
            kind="scalar"
            source_res=""
            predicted_bytes="${actual_bytes}"
        else
            kind="spatial"
            if src_res="$(detect_res_from_dims "${domain}" "${dims}")"; then
                source_res="${src_res}"
                read -r sx sy <<< "${dims}"
                source_points=$(( sx * sy ))
                predicted_bytes=$(( actual_bytes * target_points / source_points ))
                if [[ "${source_res}" -eq "${target_res}" ]]; then
                    n_spatial_matched_ontarget=$((n_spatial_matched_ontarget + 1))
                else
                    n_spatial_matched_offtarget=$((n_spatial_matched_offtarget + 1))
                fi
            else
                source_res="UNKNOWN"
                predicted_bytes="NA"
                n_spatial_unknown=$((n_spatial_unknown + 1))
            fi
        fi

        echo "${exp_dir},${var},${is_mandatory},${kind},${source_res},${actual_bytes},${predicted_bytes}" >> "${files_csv}"
        total_actual=$(( total_actual + actual_bytes ))
        [[ "${predicted_bytes}" == "NA" ]] || total_predicted=$(( total_predicted + predicted_bytes ))
    done < <(find "${exp_dir}" -mindepth 1 -maxdepth 1 -name '*.nc' -print0)

    missing=""
    for mv in ${mandatory_list}; do
        if ! grep -qw "${mv}" <<< "${present_vars}"; then
            missing="${missing}${missing:+;}${mv}"
        fi
    done
    n_missing="$(tr ';' '\n' <<< "${missing}" | grep -c . || true)"
    n_mand_present=$(( n_mand_expected - n_missing ))

    if (( n_spatial_matched_offtarget == 0 && n_spatial_unknown == 0 && n_spatial_matched_ontarget == 0 )); then
        regrid_status="no_spatial_data"
        n_no_spatial=$((n_no_spatial + 1))
    elif (( n_spatial_unknown > 0 )); then
        regrid_status="unknown_grid"
        n_unknown_grid=$((n_unknown_grid + 1))
    elif (( n_spatial_matched_offtarget > 0 )); then
        regrid_status="needs_regrid"
        n_needs_regrid=$((n_needs_regrid + 1))
    else
        regrid_status="already_at_target"
        n_already=$((n_already + 1))
    fi

    echo "${exp_dir},${n_files},${n_mand_expected},${n_mand_present},\"${missing}\",${total_actual},${total_predicted},${regrid_status}" >> "${experiments_csv}"
done < <(find_experiments "${experiments_root}" | sort)

{
    echo "domain:             ${domain}"
    echo "target_res_m:       ${target_res}"
    echo "experiments_root:   ${experiments_root}"
    echo "variables:          ${variables_filter:-(all)}"
    echo "scanned_utc:        $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "experiments_total:  ${n_exp}"
    echo "already_at_target:  ${n_already}"
    echo "needs_regrid:       ${n_needs_regrid}"
    echo "unknown_grid:       ${n_unknown_grid}"
    echo "no_spatial_data:    ${n_no_spatial}"
} > "${summary_txt}"

log "done: ${n_exp} experiment(s) scanned (${n_already} already at target, ${n_needs_regrid} need regrid, ${n_unknown_grid} unknown grid, ${n_no_spatial} no spatial data) -- ${files_csv}, ${experiments_csv}, ${summary_txt}"
