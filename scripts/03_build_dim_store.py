"""
Month 4 — Build, save, and validate the dim_store expectation suite.

Run from:  C:\\de-training\\month4
Command:   python scripts/03_build_dim_store.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import great_expectations as gx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from suites import dim_store_suite as suite_mod


DATASOURCE_NAME = "retail_warehouse_dq"
ASSET_NAME = "dim_store"
BATCH_DEF_NAME = "dim_store_whole_table"


def main() -> None:
    print(f"Loading GX context from: {PROJECT_ROOT / 'gx'}")
    context = gx.get_context(mode="file", project_root_dir=str(PROJECT_ROOT))

    suite = suite_mod.build_suite()
    print(f"\nBuilt suite '{suite.name}' with {len(suite.expectations)} expectations")

    try:
        context.suites.delete(name=suite.name)
        print(f"  -> Removed pre-existing suite '{suite.name}'")
    except Exception:
        pass
    suite = context.suites.add(suite)
    print(f"  -> Registered suite '{suite.name}' with the context")

    datasource = context.data_sources.get(DATASOURCE_NAME)
    asset = datasource.get_asset(ASSET_NAME)
    batch_def = asset.get_batch_definition(BATCH_DEF_NAME)

    vd_name = f"validate_{ASSET_NAME}"
    try:
        context.validation_definitions.delete(name=vd_name)
    except Exception:
        pass

    validation_def = context.validation_definitions.add(
        gx.ValidationDefinition(
            name=vd_name,
            data=batch_def,
            suite=suite,
        )
    )
    print(f"\nValidation definition '{vd_name}' registered")

    print(f"\nRunning validation against retaildw_dq.warehouse.{ASSET_NAME} ...")
    print("-" * 72)
    result = validation_def.run()

    pass_count = 0
    fail_count = 0
    print(f"{'#':<3} {'Result':<7} {'Dimension':<15} Expectation")
    print("-" * 72)
    for i, r in enumerate(result.results, start=1):
        status = "PASS" if r.success else "FAIL"
        dim = (r.expectation_config.meta or {}).get("dimension", "-")
        ec = r.expectation_config
        etype = ec.type if hasattr(ec, "type") else ec.expectation_type
        print(f"{i:<3} {status:<7} {dim:<15} {etype}")
        if r.success:
            pass_count += 1
        else:
            fail_count += 1

    print("-" * 72)
    total = pass_count + fail_count
    print(f"Summary: {pass_count}/{total} PASS, {fail_count}/{total} FAIL")
    print(f"Overall success: {result.success}")

    context.build_data_docs()
    docs_path = PROJECT_ROOT / "gx" / "uncommitted" / "data_docs" / "local_site" / "index.html"
    if docs_path.exists():
        print(f"\nData Docs refreshed: {docs_path}")


if __name__ == "__main__":
    main()
