#!/usr/bin/env bash
# Regrid every variable file in one ISMIP7 experiment directory onto
# a target ISMIP7 grid.
#
# Usage:
#   process_experiment.sh --domain GrIS|AIS --target-res METERS \
#       [--experiments-root ROOT] [--on-unchanged symlink|copy|skip] \
#       [--variables VAR1,VAR2,...] EXPERIMENT_DIR OUTPUT_ROOT
#
# --on-unchanged (default: symlink) controls how a file that isn't
# actually regridded (scalar variable, or already at the target
# resolution) is placed in the output -- see interpolate_variable.sh.
#
# --variables restricts processing to the given comma-separated ISMIP7
# variable names (e.g. --variables lithk,acabf), matched against the
# first '_'-separated token of each filename. If an experiment has
# none of the requested variables, that's not an error -- it's logged
# and the experiment exits 0 with nothing processed (some variables
# are optional and legitimately absent from a given experiment).
#
# Output files are written under
# OUTPUT_ROOT/<DOMAIN>_<res>m/<mirrored path>, mirroring
# EXPERIMENT_DIR's path relative to --experiments-root. If
# EXPERIMENT_DIR isn't under --experiments-root (or it wasn't given),
# the last 3 path components of EXPERIMENT_DIR are used instead
# (roughly Group/Model/experiment). Output filenames are identical to
# the source filenames -- the resolution lives in the top-level
# <DOMAIN>_<res>m directory, not in the filename.
#
# A per-experiment log is written to
# OUTPUT_ROOT/<DOMAIN>_<res>m/logs/, recording what was processed,
# the scripts' git commit, and a per-file result summary.

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

domain=""
target_res=""
experiments_root=""
on_unchanged="symlink"
variables_filter=""
positional=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain) domain="$2"; shift 2 ;;
        --target-res) target_res="$2"; shift 2 ;;
        --experiments-root) experiments_root="$2"; shift 2 ;;
        --on-unchanged) on_unchanged="$2"; shift 2 ;;
        --variables) variables_filter="$2"; shift 2 ;;
        -h|--help) grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) positional+=("$1"); shift ;;
    esac
done

[[ ${#positional[@]} -eq 2 ]] || die "usage: $(basename "$0") --domain GrIS|AIS --target-res METERS [--experiments-root ROOT] [--on-unchanged symlink|copy|skip] [--variables VAR1,VAR2,...] EXPERIMENT_DIR OUTPUT_ROOT"
experiment_dir="$(cd "${positional[0]}" && pwd)"
output_root="${positional[1]}"

[[ -n "${domain}" ]] || die "--domain is required (GrIS or AIS)"
[[ -n "${target_res}" ]] || die "--target-res is required (meters)"

# Derive the mirrored relative path.
rel_path=""
if [[ -n "${experiments_root}" ]]; then
    experiments_root="$(cd "${experiments_root}" && pwd)"
    if [[ "${experiment_dir}" == "${experiments_root}"/* ]]; then
        rel_path="${experiment_dir#"${experiments_root}"/}"
    fi
fi
if [[ -z "${rel_path}" ]]; then
    rel_path="$(echo "${experiment_dir}" | awk -F/ '{n=NF; print $(n-2)"/"$(n-1)"/"$n}')"
    log "'${experiment_dir}' is not under --experiments-root; mirroring last 3 path components: ${rel_path}"
fi

res_dir="$(res_dir_name "${domain}" "${target_res}")"
out_dir="${output_root}/${res_dir}/${rel_path}"
mkdir -p "${out_dir}"
logs_dir="${output_root}/${res_dir}/logs"
mkdir -p "${logs_dir}"

# find, not a bash glob: experiment_dir may contain shell glob
# metacharacters as literal path components (the real archive has at
# least one literal "**" directory name from a past accident), which
# a glob would re-expand instead of treating literally.
mapfile -d '' nc_files < <(find "${experiment_dir}" -mindepth 1 -maxdepth 1 -name '*.nc' -print0 | sort -z)
[[ ${#nc_files[@]} -gt 0 ]] || die "no .nc files found in ${experiment_dir}"

if [[ -n "${variables_filter}" ]]; then
    filtered=()
    for f in "${nc_files[@]}"; do
        variable_wanted "$(var_from_filename "${f}")" "${variables_filter}" && filtered+=("${f}")
    done
    nc_files=("${filtered[@]+"${filtered[@]}"}")
    if [[ ${#nc_files[@]} -eq 0 ]]; then
        log "no files matching --variables ${variables_filter} in ${experiment_dir} -- nothing to do"
        exit 0
    fi
fi

interpolate_script="$(dirname "${BASH_SOURCE[0]}")/interpolate_variable.sh"
n_fail=0
file_results=()
for in_file in "${nc_files[@]}"; do
    base="$(basename "${in_file}")"
    out_file="${out_dir}/${base}"
    if "${interpolate_script}" --domain "${domain}" --target-res "${target_res}" \
            --on-unchanged "${on_unchanged}" "${in_file}" "${out_file}"; then
        file_results+=("OK   ${base}")
    else
        log "FAIL   ${base}"
        file_results+=("FAIL ${base}")
        n_fail=$((n_fail + 1))
    fi
done

log_file="${logs_dir}/$(echo "${rel_path}" | tr '/' '_')_$(date -u '+%Y%m%dT%H%M%SZ').log"
{
    echo "experiment_dir: ${experiment_dir}"
    echo "rel_path:       ${rel_path}"
    echo "domain:         ${domain}"
    echo "target_res_m:   ${target_res}"
    echo "on_unchanged:   ${on_unchanged}"
    echo "variables:      ${variables_filter:-(all)}"
    echo "git_commit:     $(git_commit)"
    echo "started_utc:    $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "files_total:    ${#nc_files[@]}"
    echo "files_failed:   ${n_fail}"
    echo "--- per-file results ---"
    printf '%s\n' "${file_results[@]}"
} > "${log_file}"

log "done: ${#nc_files[@]} file(s) processed, ${n_fail} failed -- output in ${out_dir}, log at ${log_file}"
[[ ${n_fail} -eq 0 ]] || exit 1
