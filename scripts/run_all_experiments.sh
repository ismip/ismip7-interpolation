#!/usr/bin/env bash
# Master loop: regrid every experiment found under a root directory
# onto a target ISMIP7 grid.
#
# Usage:
#   run_all_experiments.sh --domain GrIS|AIS --target-res METERS \
#       [--experiments-root ROOT] [--output-root DIR] \
#       [--on-unchanged symlink|copy|skip] [--min-pass-pct PCT] \
#       [--variables VAR1,VAR2,...]
#
# --on-unchanged (default: symlink) controls how a file that isn't
# actually regridded (scalar variable, or already at the target
# resolution) is placed in the output -- see interpolate_variable.sh.
#
# --variables restricts processing to the given comma-separated ISMIP7
# variable names, across every experiment -- see process_experiment.sh.
#
# Not every real-archive experiment is expected to process cleanly
# (non-standard files, missing variables, etc) -- a failed experiment
# is logged and skipped, not fatal to the run. The run as a whole
# only fails if fewer than --min-pass-pct (default: 60) percent of
# experiments succeeded.
#
# An "experiment" is a directory (GROUP/MODEL/<experiment set>/
# <experiment>, e.g. NORCE/CISM/CORE/C007) matching an allowed
# experiment set and number range from config/experiment_sets.txt,
# that directly contains at least one .nc file -- see
# find_experiments() in lib/common.sh for exactly what's excluded
# (wrong/renamed experiment-set dirs, stray empty directory trees,
# etc). Each match is handed to process_experiment.sh in turn. (All
# experiments from one GROUP/MODEL together are a "submission" --
# this script operates at the experiment level, flattened across
# every submission in the archive.)
#
# --experiments-root defaults per --domain to the known archive root.

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

domain=""
target_res=""
experiments_root=""
output_root="${REPO_ROOT}/output"
on_unchanged="symlink"
min_pass_pct=60
variables_filter=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain) domain="$2"; shift 2 ;;
        --target-res) target_res="$2"; shift 2 ;;
        --experiments-root) experiments_root="$2"; shift 2 ;;
        --output-root) output_root="$2"; shift 2 ;;
        --on-unchanged) on_unchanged="$2"; shift 2 ;;
        --min-pass-pct) min_pass_pct="$2"; shift 2 ;;
        --variables) variables_filter="$2"; shift 2 ;;
        -h|--help) grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) die "unrecognized argument: $1" ;;
    esac
done

[[ -n "${domain}" ]] || die "--domain is required (GrIS or AIS)"
[[ -n "${target_res}" ]] || die "--target-res is required (meters)"

if [[ -z "${experiments_root}" ]]; then
    case "${domain}" in
        GrIS) experiments_root="/nird/datalake/NS5011K/ISMIP/ISMIP7/GrIS/ISMIP7_output/ISMIP7_submissions/GrIS" ;;
        AIS)  experiments_root="/nird/datalake/NS5011K/ISMIP/ISMIP7/AIS/ISMIP7_output/ISMIP7_submissions/AIS" ;;
    esac
fi
[[ -d "${experiments_root}" ]] || die "--experiments-root not found: ${experiments_root}"

process_script="$(dirname "${BASH_SOURCE[0]}")/process_experiment.sh"

mapfile -t experiment_dirs < <(find_experiments "${experiments_root}" | sort -u)

[[ ${#experiment_dirs[@]} -gt 0 ]] || die "no experiments found under ${experiments_root} (checked against config/experiment_sets.txt)"
log "found ${#experiment_dirs[@]} experiment(s) under ${experiments_root}"

run_started="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
n_fail=0
experiment_results=()
for dir in "${experiment_dirs[@]}"; do
    log "=== processing experiment: ${dir} ==="
    if "${process_script}" --domain "${domain}" --target-res "${target_res}" \
            --experiments-root "${experiments_root}" --on-unchanged "${on_unchanged}" \
            --variables "${variables_filter}" "${dir}" "${output_root}"; then
        experiment_results+=("OK   ${dir}")
    else
        log "FAIL   experiment: ${dir}"
        experiment_results+=("FAIL ${dir}")
        n_fail=$((n_fail + 1))
    fi
done

n_total=${#experiment_dirs[@]}
n_pass=$(( n_total - n_fail ))
pass_pct=$(( n_pass * 100 / n_total ))

res_dir="$(res_dir_name "${domain}" "${target_res}")"
logs_dir="${output_root}/${res_dir}/logs"
mkdir -p "${logs_dir}"
run_log="${logs_dir}/run_$(date -u '+%Y%m%dT%H%M%SZ').log"
{
    echo "domain:            ${domain}"
    echo "target_res_m:      ${target_res}"
    echo "experiments_root:  ${experiments_root}"
    echo "on_unchanged:      ${on_unchanged}"
    echo "variables:         ${variables_filter:-(all)}"
    echo "min_pass_pct:      ${min_pass_pct}"
    echo "git_commit:        $(git_commit)"
    echo "started_utc:       ${run_started}"
    echo "finished_utc:      $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "experiments_total: ${n_total}"
    echo "experiments_passed: ${n_pass}"
    echo "pass_pct:          ${pass_pct}"
    echo "--- per-experiment results (see logs/ for each experiment's own file-level log) ---"
    printf '%s\n' "${experiment_results[@]}"
} > "${run_log}"

log "done: ${n_pass}/${n_total} experiment(s) passed (${pass_pct}%) -- output under ${output_root}/${res_dir}, run log at ${run_log}"
[[ ${pass_pct} -ge ${min_pass_pct} ]] || die "pass rate ${pass_pct}% is below --min-pass-pct ${min_pass_pct}%"
