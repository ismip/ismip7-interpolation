#!/usr/bin/env bash
# Shared helpers for the ISMIP7 interpolation scripts.
# Source this from other scripts: `source "$(dirname "$0")/lib/common.sh"`

set -euo pipefail

SCRIPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_LIB_DIR}/../.." && pwd)"
GDF_DIR="${REPO_ROOT}/gdfs"
BILINEAR_VARS_FILE="${REPO_ROOT}/config/bilinear_variables.txt"
NEAREST_VARS_FILE="${NEAREST_VARS_FILE:-${REPO_ROOT}/config/nearest_variables.txt}"
SCALAR_VARS_FILE="${REPO_ROOT}/config/scalar_variables.txt"
MASK_MISSING_VARS_FILE="${REPO_ROOT}/config/mask_missing_variables.txt"
EXPERIMENT_SETS_FILE="${REPO_ROOT}/config/experiment_sets.txt"
VARIABLE_CSV="${REPO_ROOT}/config/ISMIP7_variable_request.csv"
# Overridable so smoke tests can point this at a throwaway directory
# instead of generating real weight files into the checked-out repo.
WEIGHTS_DIR="${WEIGHTS_DIR:-${REPO_ROOT}/weights}"

log() { echo "[$(date '+%H:%M:%S')] $*" >&2; }
die() { echo "ERROR: $*" >&2; exit 1; }

# Make sure `cdo` is on PATH. On NIRD this comes from the `nc` conda
# env; if `cdo` is already available (e.g. a future CI box with it on
# PATH) skip activation entirely rather than failing.
ensure_cdo() {
    if command -v cdo >/dev/null 2>&1; then
        return 0
    fi
    local conda_base
    conda_base="$(conda info --base 2>/dev/null)" \
        || die "cdo not on PATH and conda not found -- activate the 'nc' env yourself"
    # conda's own activation scripts (e.g. magics-activate.sh) reference
    # unset variables, which trips our `set -u` -- relax it just for
    # activation.
    set +u
    # shellcheck disable=SC1091
    source "${conda_base}/etc/profile.d/conda.sh"
    conda activate nc
    set -u
    command -v cdo >/dev/null 2>&1 || die "cdo still not on PATH after 'conda activate nc'"
}
ensure_cdo

# res_dir_name DOMAIN RES_M -> "<DOMAIN>_<res>m", e.g. "GrIS_04000m".
# The top-level output directory name for a given domain/resolution
# run -- output is written under OUTPUT_ROOT/<res_dir_name>/..., with
# a "logs/" subdirectory alongside the mirrored group directories.
res_dir_name() {
    local domain="$1" res_m="$2"
    echo "${domain}_$(printf '%05d' "${res_m}")m"
}

# git_commit -> short commit hash of the scripts repo, or a clear
# placeholder if it isn't a git repository (yet) / git isn't
# available. Never fails the caller.
git_commit() {
    if command -v git >/dev/null 2>&1 \
            && git -C "${REPO_ROOT}" rev-parse --short HEAD >/dev/null 2>&1; then
        git -C "${REPO_ROOT}" rev-parse --short HEAD
    else
        echo "unknown (not a git repository)"
    fi
}

# gdf_path DOMAIN RES_M -> path to the matching grid description file
gdf_path() {
    local domain="$1" res_m="$2"
    local f
    f="${GDF_DIR}/gdf_ISMIP7_${domain}_$(printf '%05d' "${res_m}")m.txt"
    [[ -f "${f}" ]] || die "no GDF for domain=${domain} res=${res_m}m (expected ${f})"
    echo "${f}"
}

# gdf_dims GDF_FILE -> "xsize ysize"
gdf_dims() {
    local f="$1"
    local xsize ysize
    xsize="$(awk -F'=' '/^ *xsize/ {gsub(/ /,"",$2); print $2}' "${f}")"
    ysize="$(awk -F'=' '/^ *ysize/ {gsub(/ /,"",$2); print $2}' "${f}")"
    [[ -n "${xsize}" && -n "${ysize}" ]] || die "could not parse xsize/ysize from ${f}"
    echo "${xsize} ${ysize}"
}

# parse_griddes_dims -> reads `cdo griddes` output on stdin, prints
# "xsize ysize" (empty if none found). Pure text-parsing, no cdo call
# -- kept separate from nc_dims() so it's unit-testable without cdo
# or a real NetCDF file.
#
# `cdo griddes` prints one block per gridID in the file, and files
# commonly also carry a bounds pseudo-grid (gridsize=2, xsize=2, no
# ysize -- e.g. for time_bnds) alongside the real spatial grid. Only
# the first block that actually has *both* xsize and ysize is the
# real x,y grid; a naive first-match on xsize alone picks up the
# bounds grid instead.
parse_griddes_dims() {
    awk -F'=' '
        /^ *xsize/ { gsub(/ /,"",$2); x=$2 }
        /^ *ysize/ { gsub(/ /,"",$2); y=$2 }
        /^# gridID/ { if (x != "" && y != "") { print x, y; exit }; x=""; y="" }
        END { if (x != "" && y != "") print x, y }
    '
}

# nc_dims NCFILE -> "xsize ysize" (empty if the file opens fine but
# has no x,y grid, e.g. a scalar time-series variable). Fails loudly
# (via die) if cdo can't even open the file -- the real archive has
# at least one stray non-ISMIP7 file ("lonlat__GrIS_..., "Unsupported
# file structure") that must not be silently misread as a valid
# scalar variable. Callers that scan many files across an archive
# (e.g. inventory_archive.sh) must guard this call per-file so one
# bad file doesn't abort the whole scan of experiments.
nc_dims() {
    local f="$1"
    local desc
    if ! desc="$(cdo -s griddes "${f}" 2>&1)"; then
        die "cdo could not read a grid from ${f} (corrupt or non-standard file?): ${desc}"
    fi
    parse_griddes_dims <<< "${desc}"
}

# parse_ncdump_dims -> reads `ncdump -h` output on stdin, prints
# "xsize ysize" for dimensions literally named x/y (empty if either
# is absent, e.g. a scalar time-series variable). Pure text parsing,
# no ncdump call -- unit-testable without a real NetCDF file.
parse_ncdump_dims() {
    awk '
        /^dimensions:/ { in_dims=1; next }
        /^variables:/  { in_dims=0 }
        in_dims {
            line = $0
            sub(/^[ \t]+/, "", line)
            split(line, parts, "=")
            name = parts[1]
            sub(/[ \t]+$/, "", name)
            if (name == "x") { val = parts[2]; gsub(/[^0-9]/, "", val); x = val }
            if (name == "y") { val = parts[2]; gsub(/[^0-9]/, "", val); y = val }
        }
        END { if (x != "" && y != "") print x, y }
    '
}

# nc_dims_fast NCFILE -> "xsize ysize", using `ncdump -h` instead of
# `cdo griddes`. `ncdump -h` reads only the declared header/metadata,
# not file content, so it's ~200x faster than cdo (measured: 4s vs
# 0.02s on a 1.2GB real experiment file) and its runtime doesn't scale
# with file size. It also doesn't care about dimension order the way
# cdo's CDI library does, so it correctly reads files cdo refuses to
# open (the real archive has a group, UB/ISSM, whose files trip cdo's
# "time must be first dimension" check on every file).
#
# ONLY used by inventory_archive.sh (a read-only scan) -- the actual
# regrid path (detect_source_res, used by interpolate_variable.sh /
# process_experiment.sh) deliberately keeps using cdo-based nc_dims,
# since cdo is what actually performs the regrid and a file ncdump
# can read but cdo's remap engine can't would still need to fail
# there anyway.
nc_dims_fast() {
    local f="$1"
    local hdr
    if ! hdr="$(ncdump -h "${f}" 2>&1)"; then
        die "ncdump could not read ${f} (corrupt or non-standard file?): ${hdr}"
    fi
    parse_ncdump_dims <<< "${hdr}"
}

# file_size FILE -> size in bytes (portable between GNU and BSD stat)
file_size() {
    stat -c%s "$1" 2>/dev/null || stat -f%z "$1"
}

# place_unchanged IN OUT MODE -- put a file that isn't being
# regridded (already at the target resolution, or a scalar variable
# with no spatial grid at all) into place at OUT. MODE is
# "symlink" (default elsewhere), "copy", or "skip" (write nothing).
# Symlinks point at an absolute path so they resolve regardless of
# OUT's location.
place_unchanged() {
    local in_file="$1" out_file="$2" mode="$3"
    case "${mode}" in
        symlink)
            local in_abs
            in_abs="$(cd "$(dirname "${in_file}")" && pwd)/$(basename "${in_file}")"
            ln -sf "${in_abs}" "${out_file}"
            ;;
        copy)
            cp "${in_file}" "${out_file}"
            ;;
        skip)
            : # write nothing
            ;;
        *)
            die "place_unchanged: unknown mode '${mode}' (expected symlink, copy or skip)"
            ;;
    esac
}

# mandatory_variables -> one ISMIP7 variable name per line, for every
# row marked Mandatory=yes in config/ISMIP7_variable_request.csv.
# Uses python's csv module rather than hand-rolled awk/cut splitting
# because the CSV's Dim column ("x,y,t") contains embedded commas
# inside quotes.
mandatory_variables() {
    python3 - "${VARIABLE_CSV}" <<'PY'
import csv, sys
with open(sys.argv[1], newline="") as f:
    for row in csv.DictReader(f):
        if row["Mandatory (yes/no)"].strip().lower() == "yes":
            print(row["Variable Name"].strip())
PY
}

# detect_res_from_dims DOMAIN "XSIZE YSIZE" -> resolution in meters,
# matched against every GDF for that domain. Prints nothing and
# returns non-zero if none match. Shared by detect_source_res
# (cdo-based dims) and detect_source_res_fast (ncdump-based dims).
detect_res_from_dims() {
    local domain="$1" dims="$2"
    local gdf dims_gdf res
    for gdf in "${GDF_DIR}"/gdf_ISMIP7_${domain}_*.txt; do
        [[ -f "${gdf}" ]] || continue
        dims_gdf="$(gdf_dims "${gdf}")"
        if [[ "${dims_gdf}" == "${dims}" ]]; then
            res="$(basename "${gdf}" | sed -E "s/gdf_ISMIP7_${domain}_0*([0-9]+)m\.txt/\1/")"
            echo "${res}"
            return 0
        fi
    done
    return 1
}

# detect_source_res DOMAIN NCFILE -> resolution in meters (via cdo
# griddes/nc_dims). Fails loudly if no known GDF matches -- we never
# guess a source grid. This is what the actual regrid scripts use.
detect_source_res() {
    local domain="$1" ncfile="$2"
    local dims res
    dims="$(nc_dims "${ncfile}")"
    [[ -n "${dims// /}" ]] || die "${ncfile} has no x,y grid (scalar variable?) -- can't detect a resolution"
    res="$(detect_res_from_dims "${domain}" "${dims}")" \
        || die "no ${domain} GDF matches grid dims (${dims}) of ${ncfile} -- non-standard source grid?"
    echo "${res}"
}

# detect_source_res_fast DOMAIN NCFILE -> resolution in meters (via
# ncdump -h/nc_dims_fast). Same contract as detect_source_res, just
# much faster -- see nc_dims_fast. Used only by inventory_archive.sh.
detect_source_res_fast() {
    local domain="$1" ncfile="$2"
    local dims res
    dims="$(nc_dims_fast "${ncfile}")"
    [[ -n "${dims// /}" ]] || die "${ncfile} has no x,y grid (scalar variable?) -- can't detect a resolution"
    res="$(detect_res_from_dims "${domain}" "${dims}")" \
        || die "no ${domain} GDF matches grid dims (${dims}) of ${ncfile} -- non-standard source grid?"
    echo "${res}"
}

# var_from_filename FILE -> ISMIP7 variable name (first '_'-separated
# token of the basename, matching the observed experiment naming
# convention <var>_<domain>_<institute>_<model>_....nc)
var_from_filename() {
    basename "$1" | cut -d'_' -f1
}

# list contains: NEEDLE FILE -> 0 if NEEDLE is a line in FILE
list_contains() {
    local needle="$1" file="$2"
    grep -qxF "${needle}" "${file}" 2>/dev/null
}

# variable_wanted VARNAME VARS_CSV -> 0 if VARNAME is one of the
# comma-separated names in VARS_CSV, or if VARS_CSV is empty (empty
# means "no filter, every variable is wanted").
variable_wanted() {
    local var="$1" vars_csv="$2"
    [[ -z "${vars_csv}" ]] && return 0
    local w
    local IFS=','
    for w in ${vars_csv}; do
        [[ "${var}" == "${w}" ]] && return 0
    done
    return 1
}

# find_experiments ROOT -> one path per line: every experiment
# directory under ROOT (GROUP/MODEL/<experiment set>/<experiment>,
# e.g. NORCE/CISM/CORE/C007 -- all experiments from one group+model
# combination together are a "submission"; a single experiment
# directory is not) that belongs to an allowed experiment set (see
# config/experiment_sets.txt) with an experiment number in the
# configured range, AND that directly contains at least one .nc file.
# The .nc-file requirement is what excludes real-but-empty directory
# trees -- e.g. the archive has a couple of `**/CORE/C0NN/` paths
# (literal "**" as a directory name, an accidental unexpanded-glob
# artifact) that contain only a stray `Users/...` subdirectory and no
# data directly inside; those must never be treated as an experiment.
#
# Also excludes any experiment-set dir with an "old_core"/"core_old"
# (case-insensitive) ancestor anywhere above it, not just as its own
# immediate name -- the archive has at least one case
# (.../old_CORE/CORE/C001) where a live-looking "CORE" dir is nested
# *inside* a deprecated "old_CORE" one.
find_experiments() {
    local root="$1"
    local set_name prefix min max set_dir exp_dir exp_name num
    while read -r set_name prefix min max; do
        [[ -z "${set_name}" || "${set_name}" == \#* ]] && continue
        while IFS= read -r -d '' set_dir; do
            local set_dir_lc
            set_dir_lc="$(tr '[:upper:]' '[:lower:]' <<< "${set_dir}")"
            if [[ "${set_dir_lc}" == *old_core* || "${set_dir_lc}" == *core_old* ]]; then
                continue
            fi
            while IFS= read -r -d '' exp_dir; do
                exp_name="$(basename "${exp_dir}")"
                [[ "${exp_name}" =~ ^${prefix}([0-9]{3})$ ]] || continue
                num=$((10#${BASH_REMATCH[1]}))
                (( num >= min && num <= max )) || continue
                # Use `find`, not a bash glob: some real archive paths
                # contain a literal "**" directory component (an
                # accidental unexpanded-glob artifact), which a bash
                # glob would itself re-expand as a wildcard.
                [[ -n "$(find "${exp_dir}" -mindepth 1 -maxdepth 1 -name '*.nc' -print -quit)" ]] || continue
                echo "${exp_dir}"
            done < <(find "${set_dir}" -mindepth 1 -maxdepth 1 -type d -print0)
        done < <(find "${root}" -type d -name "${set_name}" -print0 2>/dev/null)
    done < "${EXPERIMENT_SETS_FILE}"
}

# interp_method VARNAME -> "copy" | "bil" | "nn" | "ycon"
interp_method() {
    local var="$1"
    if list_contains "${var}" "${SCALAR_VARS_FILE}"; then
        echo "copy"
    elif list_contains "${var}" "${BILINEAR_VARS_FILE}"; then
        echo "bil"
    elif list_contains "${var}" "${NEAREST_VARS_FILE}"; then
        echo "nn"
    else
        echo "ycon"
    fi
}

# use_setmisstoc VARNAME -> 0 if VARNAME's missing source cells may be
# filled with 0 (`cdo setmisstoc,0`) before remapping, 1 if its actual
# missing-value pattern must be preserved instead.
# config/mask_missing_variables.txt is the exclude list (default:
# setmisstoc is fine); see that file for why -- in short, filling
# makes the source mask uniform across timesteps/files, which is what
# lets remap weights be precomputed once per (domain, source_res,
# target_res, method) and reused (see ensure_weights below) instead of
# cdo recomputing them per file/timestep whenever the mask differs.
use_setmisstoc() {
    local var="$1"
    if list_contains "${var}" "${MASK_MISSING_VARS_FILE}"; then
        return 1
    else
        return 0
    fi
}

# has_missing_values NCFILE -> 0 if the file has at least one missing
# value anywhere (any variable/timestep), 1 if none. `cdo info`'s Miss
# column (field 7 of each data row: "N : Date Time Level Gridsize
# Miss : Min Mean Max : Name") gives this; this cdo build has no
# dedicated `nmiss` operator to shortcut it. Used to let a variable
# listed in config/mask_missing_variables.txt still use the cached
# full-grid weights when its actual data has no missing values to
# preserve in the first place.
has_missing_values() {
    local f="$1"
    local total
    total="$(cdo -s info "${f}" 2>/dev/null | awk 'NR>1 {sum+=$7} END{print sum+0}')"
    [[ "${total}" -gt 0 ]]
}

# weight_file_path DOMAIN SOURCE_RES_M TARGET_RES_M METHOD -> path to
# the cached remap weight file for that combination, e.g.
# weights/GrIS_01000m_to_04000m_ycon.nc. One file is shared across
# every variable/experiment on that resolution pair and method, since
# (once setmisstoc,0 removes the data-dependent missing-value mask)
# the weights depend only on the two grids' geometry.
weight_file_path() {
    local domain="$1" source_res="$2" target_res="$3" method="$4"
    printf '%s/%s_%sm_to_%sm_%s.nc' "${WEIGHTS_DIR}" "${domain}" \
        "$(printf '%05d' "${source_res}")" "$(printf '%05d' "${target_res}")" "${method}"
}

# ensure_weights DOMAIN SOURCE_RES_M TARGET_RES_M METHOD -> path to a
# ready-to-use weight file, generating it on first use (see
# weight_file_path) and reusing it on every later call. Generated from
# a synthetic constant field on the source grid (`cdo const`), not
# from any real archive file -- a real sample isn't needed since the
# weights depend only on grid geometry, and this keeps the (read-only)
# archive out of the loop entirely. Written via a temp file + atomic
# `mv` so a crash mid-generation never leaves a corrupt file at the
# final path; a rare concurrent-generation race just recomputes the
# same deterministic weights twice, which is wasteful but harmless.
ensure_weights() {
    local domain="$1" source_res="$2" target_res="$3" method="$4"
    local wfile
    wfile="$(weight_file_path "${domain}" "${source_res}" "${target_res}" "${method}")"
    if [[ -f "${wfile}" ]]; then
        echo "${wfile}"
        return 0
    fi

    mkdir -p "${WEIGHTS_DIR}"
    local source_gdf target_gdf gen_op tmpdir
    source_gdf="$(gdf_path "${domain}" "${source_res}")"
    target_gdf="$(gdf_path "${domain}" "${target_res}")"
    gen_op="genycon"
    case "${method}" in
        bil) gen_op="genbil" ;;
        nn)  gen_op="gennn" ;;
    esac

    tmpdir="$(mktemp -d "${WEIGHTS_DIR}/.gen_XXXXXX")"
    log "generating remap weights: ${domain} ${source_res}m -> ${target_res}m (${method}) -> ${wfile}"
    # cdo writes its own progress/diagnostic messages to stdout (not
    # just stderr) -- redirect them to fd 2 so they don't corrupt the
    # path this function returns via stdout to its `$(...)` caller.
    cdo -f nc const,1,"${source_gdf}" "${tmpdir}/template.nc" >&2
    cdo "${gen_op}","${target_gdf}" "${tmpdir}/template.nc" "${tmpdir}/weights.nc" >&2
    mv "${tmpdir}/weights.nc" "${wfile}"
    rm -rf "${tmpdir}"
    echo "${wfile}"
}
