# Unit tests for scripts/lib/common.sh -- pure logic only, no cdo and
# no real NetCDF files (so these run on any box with bash+python3,
# including plain GitHub Actions runners).

setup() {
    REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
    # common.sh calls ensure_cdo() at source time; stub it out so
    # these tests don't need cdo (or conda) on PATH at all.
    ensure_cdo() { :; }
    export -f ensure_cdo
    source "${REPO_ROOT}/scripts/lib/common.sh"
}

# --- res_dir_name / git_commit --------------------------------------

@test "res_dir_name formats domain and resolution" {
    run res_dir_name GrIS 4000
    [ "$output" = "GrIS_04000m" ]
    run res_dir_name AIS 8000
    [ "$output" = "AIS_08000m" ]
}

@test "git_commit never fails, regardless of whether this is a git repo yet" {
    run git_commit
    [ "$status" -eq 0 ]
    # Either a short hex commit hash, or the explicit not-a-repo message
    # -- this repo may or may not have git initialized at test time.
    [[ "$output" =~ ^[0-9a-f]{4,40}$ ]] || [[ "$output" == "unknown (not a git repository)" ]]
}

# --- gdf_path / gdf_dims -----------------------------------------

@test "gdf_path resolves a known GrIS resolution" {
    run gdf_path GrIS 4000
    [ "$status" -eq 0 ]
    [ "$output" = "${REPO_ROOT}/gdfs/gdf_ISMIP7_GrIS_04000m.txt" ]
}

@test "gdf_path fails loudly for an unknown resolution" {
    run gdf_path GrIS 3000
    [ "$status" -ne 0 ]
    [[ "$output" == *"no GDF"* ]]
}

@test "detect_res_from_dims matches a known GrIS resolution" {
    run detect_res_from_dims GrIS "421 721"
    [ "$status" -eq 0 ]
    [ "$output" = "4000" ]
}

@test "detect_res_from_dims fails (non-zero, no output) for unmatched dims" {
    run detect_res_from_dims GrIS "999 999"
    [ "$status" -ne 0 ]
}

@test "gdf_dims parses xsize/ysize from a real GDF file" {
    run gdf_dims "${REPO_ROOT}/gdfs/gdf_ISMIP7_GrIS_04000m.txt"
    [ "$status" -eq 0 ]
    [ "$output" = "421 721" ]
}

# --- parse_griddes_dims --------------------------------------------

@test "parse_griddes_dims picks the spatial grid over a bounds pseudo-grid" {
    # Mirrors real `cdo griddes` output on ISMIP7 files: a bounds
    # grid (gridsize=2, xsize=2, no ysize) followed by the real x,y
    # grid -- the bounds block must not be mistaken for the real one.
    run parse_griddes_dims <<'EOF'
#
# gridID 1
#
gridtype  = generic
gridsize  = 2
xsize     = 2
xdimname  = bnds
#
# gridID 2
#
gridtype  = generic
gridsize  = 303541
xsize     = 421
ysize     = 721
EOF
    [ "$status" -eq 0 ]
    [ "$output" = "421 721" ]
}

@test "parse_griddes_dims returns empty for a scalar (gridsize=1) file" {
    run parse_griddes_dims <<'EOF'
#
# gridID 1
#
gridtype  = generic
gridsize  = 1
EOF
    [ "$status" -eq 0 ]
    [ "$output" = "" ]
}

# --- parse_ncdump_dims ------------------------------------------------

@test "parse_ncdump_dims reads x/y dimensions regardless of declaration order" {
    run parse_ncdump_dims <<'EOF'
netcdf lithk_GrIS_NORCE_CISM3 {
dimensions:
	time = UNLIMITED ; // (286 currently)
	x = 421 ;
	y = 721 ;
variables:
	double lithk(time, y, x) ;
}
EOF
    [ "$status" -eq 0 ]
    [ "$output" = "421 721" ]
}

@test "parse_ncdump_dims ignores unrelated dimensions like nv/bnds" {
    run parse_ncdump_dims <<'EOF'
netcdf acabf {
dimensions:
	time = UNLIMITED ;
	y = 2881 ;
	x = 1681 ;
	nv = 2 ;
variables:
	double acabf(time, y, x) ;
}
EOF
    [ "$status" -eq 0 ]
    [ "$output" = "1681 2881" ]
}

@test "parse_ncdump_dims returns empty for a scalar (t-only) file" {
    run parse_ncdump_dims <<'EOF'
netcdf lim {
dimensions:
	time = UNLIMITED ;
variables:
	float lim(time) ;
}
EOF
    [ "$status" -eq 0 ]
    [ "$output" = "" ]
}

# --- var_from_filename ---------------------------------------------

@test "var_from_filename extracts the variable from the real archive naming convention" {
    run var_from_filename "acabf_GrIS_NORCE_CISM3_m001_CESM2-WACCM_f001_ssp585_C007_2015-2300.nc"
    [ "$status" -eq 0 ]
    [ "$output" = "acabf" ]
}

# --- place_unchanged --------------------------------------------------

@test "place_unchanged symlink creates a resolvable absolute symlink" {
    in_dir="${BATS_TEST_TMPDIR}/in"
    out_dir="${BATS_TEST_TMPDIR}/out"
    mkdir -p "${in_dir}" "${out_dir}"
    echo "data" > "${in_dir}/src.nc"

    run place_unchanged "${in_dir}/src.nc" "${out_dir}/dst.nc" symlink
    [ "$status" -eq 0 ]
    [ -L "${out_dir}/dst.nc" ]
    [ "$(cat "${out_dir}/dst.nc")" = "data" ]
    # Target must be absolute so the link resolves regardless of cwd.
    [[ "$(readlink "${out_dir}/dst.nc")" == /* ]]
}

@test "place_unchanged copy makes a real file, not a symlink" {
    in_dir="${BATS_TEST_TMPDIR}/in"
    mkdir -p "${in_dir}"
    echo "data" > "${in_dir}/src.nc"

    run place_unchanged "${in_dir}/src.nc" "${BATS_TEST_TMPDIR}/dst.nc" copy
    [ "$status" -eq 0 ]
    [ -f "${BATS_TEST_TMPDIR}/dst.nc" ]
    [ ! -L "${BATS_TEST_TMPDIR}/dst.nc" ]
}

@test "place_unchanged skip writes nothing" {
    in_dir="${BATS_TEST_TMPDIR}/in"
    mkdir -p "${in_dir}"
    echo "data" > "${in_dir}/src.nc"

    run place_unchanged "${in_dir}/src.nc" "${BATS_TEST_TMPDIR}/dst.nc" skip
    [ "$status" -eq 0 ]
    [ ! -e "${BATS_TEST_TMPDIR}/dst.nc" ]
}

@test "place_unchanged rejects an unknown mode" {
    run place_unchanged "/tmp/a" "/tmp/b" bogus
    [ "$status" -ne 0 ]
    [[ "$output" == *"unknown mode"* ]]
}

# --- variable_wanted --------------------------------------------------

@test "variable_wanted: empty filter wants everything" {
    run variable_wanted lithk ""
    [ "$status" -eq 0 ]
}

@test "variable_wanted: matches a name in a comma-separated list" {
    run variable_wanted acabf "lithk,acabf,xvelsurf"
    [ "$status" -eq 0 ]
}

@test "variable_wanted: rejects a name not in the list" {
    run variable_wanted orog "lithk,acabf,xvelsurf"
    [ "$status" -ne 0 ]
}

# --- interp_method ---------------------------------------------------

@test "interp_method: scalar variable -> copy" {
    run interp_method lim
    [ "$output" = "copy" ]
}

@test "interp_method: velocity component -> bil" {
    run interp_method xvelsurf
    [ "$output" = "bil" ]
}

@test "interp_method: ordinary state/flux variable -> ycon" {
    run interp_method lithk
    [ "$output" = "ycon" ]
    run interp_method acabf
    [ "$output" = "ycon" ]
}

@test "interp_method: nearest-neighbor list variable -> nn" {
    # The real config/nearest_variables.txt ships empty (no variable
    # confirmed yet) -- override it with a synthetic entry to test the
    # mechanism itself.
    NEAREST_VARS_FILE="${BATS_TEST_TMPDIR}/nearest.txt"
    echo "sftgif" > "${NEAREST_VARS_FILE}"
    run interp_method sftgif
    [ "$output" = "nn" ]
}

# --- use_setmisstoc / weight_file_path --------------------------------

@test "use_setmisstoc: ordinary variable is fine to mask-fill" {
    run use_setmisstoc lithk
    [ "$status" -eq 0 ]
}

@test "use_setmisstoc: velocity component must preserve its mask" {
    run use_setmisstoc xvelsurf
    [ "$status" -ne 0 ]
}

@test "weight_file_path formats domain/resolutions/method into a stable name" {
    run weight_file_path GrIS 1000 4000 ycon
    [ "$status" -eq 0 ]
    [ "$output" = "${WEIGHTS_DIR}/GrIS_01000m_to_04000m_ycon.nc" ]
}

# --- mandatory_variables ---------------------------------------------

@test "mandatory_variables includes known mandatory vars and excludes optional ones" {
    run mandatory_variables
    [ "$status" -eq 0 ]
    [[ "$output" == *"lithk"* ]]
    [[ "$output" == *"acabf"* ]]
    # hfgeoubed is Mandatory=no in the CSV
    [[ "$output" != *"hfgeoubed"* ]]
}

# --- find_experiments -------------------------------------------------
# Builds a fake archive tree with only empty *.nc placeholders --
# find_experiments only checks directory names/structure and file
# presence, never file content.

@test "find_experiments matches CORE/C0NN in range and excludes known non-experiment paths" {
    root="${BATS_TEST_TMPDIR}/archive"

    # valid: CORE/C001
    mkdir -p "${root}/GroupA/ModelA/CORE/C001"
    touch "${root}/GroupA/ModelA/CORE/C001/lithk_GrIS_x.nc"

    # invalid: renamed/deprecated experiment-set dirs
    mkdir -p "${root}/GroupB/ModelB/old_CORE/C001"
    touch "${root}/GroupB/ModelB/old_CORE/C001/lithk_GrIS_x.nc"
    mkdir -p "${root}/GroupC/ModelC/CORE_old/C001"
    touch "${root}/GroupC/ModelC/CORE_old/C001/lithk_GrIS_x.nc"

    # invalid: CORE nested inside old_CORE ancestor
    mkdir -p "${root}/GroupD/ModelD/old_CORE/CORE/C001"
    touch "${root}/GroupD/ModelD/old_CORE/CORE/C001/lithk_GrIS_x.nc"

    # invalid: experiment number out of the configured range (1-11)
    mkdir -p "${root}/GroupE/ModelE/CORE/C012"
    touch "${root}/GroupE/ModelE/CORE/C012/lithk_GrIS_x.nc"

    # invalid: matches CORE/C0NN naming but has no .nc file directly
    # inside (mirrors the real archive's stray "**" artifact dirs)
    mkdir -p "${root}/GroupF/ModelF/CORE/C001/Users/someone"
    touch "${root}/GroupF/ModelF/CORE/C001/Users/someone/leftover.nc"

    run find_experiments "${root}"
    [ "$status" -eq 0 ]
    [[ "$output" == *"GroupA/ModelA/CORE/C001"* ]]
    [[ "$output" != *"GroupB"* ]]
    [[ "$output" != *"GroupC"* ]]
    [[ "$output" != *"GroupD"* ]]
    [[ "$output" != *"GroupE"* ]]
    [[ "$output" != *"GroupF"* ]]
    [ "$(echo "$output" | grep -c .)" -eq 1 ]
}
