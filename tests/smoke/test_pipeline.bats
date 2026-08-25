# Smoke tests for the actual cdo pipeline (interpolate_variable.sh /
# process_experiment.sh) against small synthetic fixtures. Needs a
# real `cdo` (and `ncgen` to build fixtures) on PATH -- run
# tests/fixtures/make_fixtures.sh first (the CI workflow does this).

setup() {
    REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
    # Point weight generation at a throwaway dir instead of the
    # checked-out repo's weights/, and export it so the
    # interpolate_variable.sh subprocesses launched via `run` below
    # (which source common.sh themselves) see the same override.
    export WEIGHTS_DIR="${BATS_TEST_TMPDIR}/weights"
    source "${REPO_ROOT}/scripts/lib/common.sh"
    FIXTURES_DIR="${REPO_ROOT}/tests/fixtures/data"
    [[ -d "${FIXTURES_DIR}" ]] || skip "fixtures not generated -- run tests/fixtures/make_fixtures.sh first"
    OUT_DIR="${BATS_TEST_TMPDIR}/out"
    mkdir -p "${OUT_DIR}"
    # Source grid used by the fixtures is GrIS 16km; regrid down to
    # 8km so every test actually exercises regridding (not the
    # already-at-target skip path).
    TARGET_RES=8000
}

@test "conservative regrid (state variable) lands on the target grid" {
    in="${FIXTURES_DIR}/lithk_GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc"
    [[ -f "${in}" ]] || skip "lithk fixture missing"
    out="${OUT_DIR}/lithk_out.nc"

    run "${REPO_ROOT}/scripts/interpolate_variable.sh" --domain GrIS --target-res "${TARGET_RES}" "${in}" "${out}"
    [ "$status" -eq 0 ]
    [[ "$output" == *"REGRID"* ]]
    [[ "$output" == *"via remapycon"* ]]

    [ -f "${out}" ]
    dims="$(nc_dims "${out}")"
    [ "${dims}" = "211 361" ]
}

@test "flux variable also regrids conservatively" {
    in="${FIXTURES_DIR}/acabf_GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc"
    [[ -f "${in}" ]] || skip "acabf fixture missing"
    out="${OUT_DIR}/acabf_out.nc"

    run "${REPO_ROOT}/scripts/interpolate_variable.sh" --domain GrIS --target-res "${TARGET_RES}" "${in}" "${out}"
    [ "$status" -eq 0 ]
    [ -f "${out}" ]
}

@test "velocity component (bilinear exception) regrids via remapbil" {
    in="${FIXTURES_DIR}/xvelsurf_GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc"
    [[ -f "${in}" ]] || skip "xvelsurf fixture missing"
    out="${OUT_DIR}/xvelsurf_out.nc"

    run "${REPO_ROOT}/scripts/interpolate_variable.sh" --domain GrIS --target-res "${TARGET_RES}" "${in}" "${out}"
    [ "$status" -eq 0 ]
    [[ "$output" == *"remapbil"* ]]
    [ -f "${out}" ]
}

@test "--method nn forces nearest-neighbor regridding via cached weights" {
    # config/nearest_variables.txt ships empty (no variable confirmed
    # yet) -- use the explicit --method override to exercise the
    # remapnn/gennn mechanism itself against a real fixture.
    in="${FIXTURES_DIR}/lithk_GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc"
    [[ -f "${in}" ]] || skip "lithk fixture missing"
    out="${OUT_DIR}/lithk_nn_out.nc"

    run "${REPO_ROOT}/scripts/interpolate_variable.sh" --domain GrIS --target-res "${TARGET_RES}" --method nn "${in}" "${out}"
    [ "$status" -eq 0 ]
    [[ "$output" == *"via remapnn"* ]]
    [[ "$output" == *"cached weights"* ]]
    [ -f "${out}" ]
    wfile="$(weight_file_path GrIS 16000 8000 nn)"
    [ -f "${wfile}" ]
}

@test "cached weights: default variable generates once and reuses a shared weight file" {
    in_lithk="${FIXTURES_DIR}/lithk_GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc"
    in_acabf="${FIXTURES_DIR}/acabf_GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc"
    [[ -f "${in_lithk}" && -f "${in_acabf}" ]] || skip "lithk/acabf fixtures missing"

    run "${REPO_ROOT}/scripts/interpolate_variable.sh" --domain GrIS --target-res "${TARGET_RES}" "${in_lithk}" "${OUT_DIR}/lithk_out.nc"
    [ "$status" -eq 0 ]
    [[ "$output" == *"cached weights"* ]]
    [[ "$output" == *"generating remap weights"* ]]
    wfile="$(weight_file_path GrIS 16000 8000 ycon)"
    [ -f "${wfile}" ]

    # A different variable sharing the same (source_res, target_res,
    # method) triple must reuse the weight file, not regenerate it.
    run "${REPO_ROOT}/scripts/interpolate_variable.sh" --domain GrIS --target-res "${TARGET_RES}" "${in_acabf}" "${OUT_DIR}/acabf_out.nc"
    [ "$status" -eq 0 ]
    [[ "$output" == *"cached weights"* ]]
    [[ "$output" != *"generating remap weights"* ]]
}

@test "mask-missing variable with real missing values skips the weight cache" {
    in="${FIXTURES_DIR}/yvelsurf_GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc"
    [[ -f "${in}" ]] || skip "yvelsurf fixture missing"
    out="${OUT_DIR}/yvelsurf_out.nc"

    run "${REPO_ROOT}/scripts/interpolate_variable.sh" --domain GrIS --target-res "${TARGET_RES}" "${in}" "${out}"
    [ "$status" -eq 0 ]
    [[ "$output" == *"missing-value mask preserved"* ]]
    [[ "$output" == *"remapbil"* ]]
    [ -f "${out}" ]
}

@test "mask-missing variable with no actual missing values still uses cached weights" {
    in="${FIXTURES_DIR}/xvelsurf_GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc"
    [[ -f "${in}" ]] || skip "xvelsurf fixture missing"
    out="${OUT_DIR}/xvelsurf_out.nc"

    run "${REPO_ROOT}/scripts/interpolate_variable.sh" --domain GrIS --target-res "${TARGET_RES}" "${in}" "${out}"
    [ "$status" -eq 0 ]
    [[ "$output" == *"cached weights"* ]]
    [ -f "${out}" ]
    wfile="$(weight_file_path GrIS 16000 8000 bil)"
    [ -f "${wfile}" ]
}

@test "scalar variable defaults to a symlink, not a copy" {
    in="${FIXTURES_DIR}/lim_GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc"
    [[ -f "${in}" ]] || skip "lim fixture missing"
    out="${OUT_DIR}/lim_out.nc"

    run "${REPO_ROOT}/scripts/interpolate_variable.sh" --domain GrIS --target-res "${TARGET_RES}" "${in}" "${out}"
    [ "$status" -eq 0 ]
    [[ "$output" == *"SYMLINK"* ]]
    [ -L "${out}" ]
    cmp -s "${in}" "${out}"
}

@test "already-at-target-resolution file defaults to a symlink, not a copy" {
    in="${FIXTURES_DIR}/lithk_GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc"
    [[ -f "${in}" ]] || skip "lithk fixture missing"
    out="${OUT_DIR}/lithk_same_res.nc"

    # Fixtures are already on the 16km grid -- target the same res.
    run "${REPO_ROOT}/scripts/interpolate_variable.sh" --domain GrIS --target-res 16000 "${in}" "${out}"
    [ "$status" -eq 0 ]
    [[ "$output" == *"SYMLINK"* ]]
    [ -L "${out}" ]
    cmp -s "${in}" "${out}"
}

@test "--on-unchanged copy makes a real copy, not a symlink" {
    in="${FIXTURES_DIR}/lithk_GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc"
    [[ -f "${in}" ]] || skip "lithk fixture missing"
    out="${OUT_DIR}/lithk_copy.nc"

    run "${REPO_ROOT}/scripts/interpolate_variable.sh" --domain GrIS --target-res 16000 --on-unchanged copy "${in}" "${out}"
    [ "$status" -eq 0 ]
    [[ "$output" == *"COPY"* ]]
    [ -f "${out}" ]
    [ ! -L "${out}" ]
    cmp -s "${in}" "${out}"
}

@test "--on-unchanged skip writes nothing" {
    in="${FIXTURES_DIR}/lithk_GrIS_TEST_MODEL_m001_ESM_f001_ssp585_C001_2015-2015.nc"
    [[ -f "${in}" ]] || skip "lithk fixture missing"
    out="${OUT_DIR}/lithk_skip.nc"

    run "${REPO_ROOT}/scripts/interpolate_variable.sh" --domain GrIS --target-res 16000 --on-unchanged skip "${in}" "${out}"
    [ "$status" -eq 0 ]
    [[ "$output" == *"SKIP"* ]]
    [ ! -e "${out}" ]
}

@test "process_experiment.sh regrids every file in a directory and reports failures" {
    [[ -d "${FIXTURES_DIR}" ]] || skip "fixtures missing"
    exp_dir="${BATS_TEST_TMPDIR}/experiment"
    mkdir -p "${exp_dir}"
    cp "${FIXTURES_DIR}"/*.nc "${exp_dir}/"

    run "${REPO_ROOT}/scripts/process_experiment.sh" --domain GrIS --target-res "${TARGET_RES}" "${exp_dir}" "${OUT_DIR}/mirrored"
    [ "$status" -eq 0 ]
    [[ "$output" == *"0 failed"* ]]

    # Output lives under a top-level <DOMAIN>_<res>m directory, with
    # filenames identical to the source (no resolution suffix).
    res_dir="${OUT_DIR}/mirrored/GrIS_08000m"
    [ -d "${res_dir}" ]
    out_count="$(find "${res_dir}" -name '*.nc' -not -path '*/logs/*' | wc -l | tr -d ' ')"
    [ "${out_count}" -eq 5 ]
    src_name="$(basename "${FIXTURES_DIR}"/lithk_*.nc)"
    out_count_named="$(find "${res_dir}" -name "${src_name}" | wc -l | tr -d ' ')"
    [ "${out_count_named}" -eq 1 ]

    # A per-experiment log was written under logs/.
    log_count="$(find "${res_dir}/logs" -name '*.log' | wc -l | tr -d ' ')"
    [ "${log_count}" -eq 1 ]
    log_file="$(find "${res_dir}/logs" -name '*.log')"
    grep -q "git_commit:" "${log_file}"
    grep -q "files_total:    5" "${log_file}"
}

@test "process_experiment.sh --variables restricts processing to the requested variables" {
    [[ -d "${FIXTURES_DIR}" ]] || skip "fixtures missing"
    exp_dir="${BATS_TEST_TMPDIR}/experiment"
    mkdir -p "${exp_dir}"
    cp "${FIXTURES_DIR}"/*.nc "${exp_dir}/"

    run "${REPO_ROOT}/scripts/process_experiment.sh" --domain GrIS --target-res "${TARGET_RES}" \
        --variables lithk,lim "${exp_dir}" "${OUT_DIR}/filtered"
    [ "$status" -eq 0 ]
    [[ "$output" == *"0 failed"* ]]

    res_dir="${OUT_DIR}/filtered/GrIS_08000m"
    out_count="$(find "${res_dir}" -name '*.nc' -not -path '*/logs/*' | wc -l | tr -d ' ')"
    [ "${out_count}" -eq 2 ]
    [ -n "$(find "${res_dir}" -name 'lithk_*.nc')" ]
    [ -n "$(find "${res_dir}" -name 'lim_*.nc')" ]
    [ -z "$(find "${res_dir}" -name 'acabf_*.nc')" ]
}

@test "process_experiment.sh --variables with no matches exits 0 and processes nothing" {
    [[ -d "${FIXTURES_DIR}" ]] || skip "fixtures missing"
    exp_dir="${BATS_TEST_TMPDIR}/experiment"
    mkdir -p "${exp_dir}"
    cp "${FIXTURES_DIR}"/*.nc "${exp_dir}/"

    run "${REPO_ROOT}/scripts/process_experiment.sh" --domain GrIS --target-res "${TARGET_RES}" \
        --variables nonexistentvar "${exp_dir}" "${OUT_DIR}/nomatch"
    [ "$status" -eq 0 ]
    [[ "$output" == *"nothing to do"* ]]
    # The output dir gets created (mkdir -p happens before filtering),
    # but nothing should have been written into it.
    [ -z "$(find "${OUT_DIR}/nomatch" -name '*.nc')" ]
}

@test "inventory_archive.sh reports file/experiment details without regridding anything" {
    [[ -d "${FIXTURES_DIR}" ]] || skip "fixtures missing"
    command -v ncdump >/dev/null 2>&1 || skip "ncdump not on PATH"

    root="${BATS_TEST_TMPDIR}/archive"
    exp_dir="${root}/TESTGROUP/TESTMODEL/CORE/C001"
    mkdir -p "${exp_dir}"
    cp "${FIXTURES_DIR}"/*.nc "${exp_dir}/"

    inv_dir="${OUT_DIR}/inventory"
    run "${REPO_ROOT}/scripts/inventory_archive.sh" --domain GrIS --target-res "${TARGET_RES}" \
        --experiments-root "${root}" --output "${inv_dir}"
    [ "$status" -eq 0 ]

    [ -f "${inv_dir}/files.csv" ]
    [ -f "${inv_dir}/experiments.csv" ]
    [ -f "${inv_dir}/summary.txt" ]

    # No output/regridded .nc files anywhere -- this is read-only.
    [ "$(find "${inv_dir}" -name '*.nc' | wc -l | tr -d ' ')" -eq 0 ]

    # 5 fixtures -> 5 file rows (+ header).
    [ "$(wc -l < "${inv_dir}/files.csv" | tr -d ' ')" -eq 6 ]
    # lim is scalar; the other 4 are spatial, all off-target (16km
    # fixtures scanned against an 8km target) -> needs_regrid.
    grep -q ",lim,.*,scalar," "${inv_dir}/files.csv"
    grep -q ",lithk,.*,spatial,16000," "${inv_dir}/files.csv"
    grep -q "needs_regrid" "${inv_dir}/experiments.csv"
    grep -q "experiments_total:  1" "${inv_dir}/summary.txt"
    grep -q "needs_regrid:       1" "${inv_dir}/summary.txt"
}

@test "inventory_archive.sh --variables restricts the scan to the requested variable" {
    [[ -d "${FIXTURES_DIR}" ]] || skip "fixtures missing"
    command -v ncdump >/dev/null 2>&1 || skip "ncdump not on PATH"

    root="${BATS_TEST_TMPDIR}/archive"
    exp_dir="${root}/TESTGROUP/TESTMODEL/CORE/C001"
    mkdir -p "${exp_dir}"
    cp "${FIXTURES_DIR}"/*.nc "${exp_dir}/"

    inv_dir="${OUT_DIR}/inventory_filtered"
    run "${REPO_ROOT}/scripts/inventory_archive.sh" --domain GrIS --target-res "${TARGET_RES}" \
        --experiments-root "${root}" --output "${inv_dir}" --variables lithk
    [ "$status" -eq 0 ]

    # Only lithk's row (+ header) -- every other fixture is skipped
    # before its ncdump call, not just filtered out of the report.
    [ "$(wc -l < "${inv_dir}/files.csv" | tr -d ' ')" -eq 2 ]
    grep -q ",lithk,.*,spatial,16000," "${inv_dir}/files.csv"
    [ -z "$(grep ',acabf,' "${inv_dir}/files.csv")" ]
    [ -z "$(grep ',lim,' "${inv_dir}/files.csv")" ]
    grep -q "variables:          lithk" "${inv_dir}/summary.txt"
}

@test "inventory_archive.sh defaults its output dir per-domain so GrIS and AIS scans don't collide" {
    [[ -d "${FIXTURES_DIR}" ]] || skip "fixtures missing"
    command -v ncdump >/dev/null 2>&1 || skip "ncdump not on PATH"

    root="${BATS_TEST_TMPDIR}/archive"
    exp_dir="${root}/TESTGROUP/TESTMODEL/CORE/C001"
    mkdir -p "${exp_dir}"
    cp "${FIXTURES_DIR}"/*.nc "${exp_dir}/"

    default_dir="${REPO_ROOT}/output/inventory_GrIS"
    rm -rf "${default_dir}"

    run "${REPO_ROOT}/scripts/inventory_archive.sh" --domain GrIS --target-res "${TARGET_RES}" \
        --experiments-root "${root}"
    [ "$status" -eq 0 ]
    [ -f "${default_dir}/summary.txt" ]

    rm -rf "${default_dir}"
}
