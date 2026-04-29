"""
Month 4 — Step 2.2: Smoke test the GX data source + batch.

Loads the GX context, fetches a batch from dim_customer, and
prints basic stats. If this runs successfully, Step 2 is done
and we're ready to write expectations in Step 3.

Run from:  C:\\de-training\\month4
Command:   python scripts/02_test_connection.py
"""

from pathlib import Path

import great_expectations as gx


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASOURCE_NAME = "retail_warehouse_dq"
TEST_ASSET = "dim_customer"
TEST_BATCH = "dim_customer_whole_table"


def main() -> None:
    print(f"Loading GX context from: {PROJECT_ROOT / 'gx'}")
    context = gx.get_context(mode="file", project_root_dir=str(PROJECT_ROOT))

    # Walk the object hierarchy: datasource -> asset -> batch definition
    print(f"\nFetching data source: {DATASOURCE_NAME}")
    datasource = context.data_sources.get(DATASOURCE_NAME)

    print(f"Fetching asset:       {TEST_ASSET}")
    asset = datasource.get_asset(TEST_ASSET)

    print(f"Fetching batch def:   {TEST_BATCH}")
    batch_def = asset.get_batch_definition(TEST_BATCH)

    print("\nMaterializing batch (executing SQL against retaildw_dq)...")
    batch = batch_def.get_batch()

    # validation_df is a pandas DataFrame of the batch's rows
    # Be cautious: full-table batch on fact_sales (500K rows) would be heavy.
    # dim_customer at 10K rows is safe.
    print("\nSmoke check: head(5) of dim_customer batch")
    print("-" * 60)
    # GX 1.x exposes the validator wrapper that in turn exposes data.
    # The direct path for a quick peek:
    head_result = batch.head(fetch_all=False, n_rows=5)
    print(head_result)

    print("\nSmoke check: row count via expectation")
    print("-" * 60)
    # Running one trivial expectation also confirms the full validation path.
    count_expectation = gx.expectations.ExpectTableRowCountToBeBetween(
        min_value=1,
        max_value=1_000_000,
    )
    result = batch.validate(count_expectation)
    print(f"  success:        {result.success}")
    print(f"  observed_value: {result.result.get('observed_value')}")

    print("\n" + "=" * 60)
    print("Data source smoke test PASSED." if result.success else
          "Data source smoke test FAILED.")
    print("=" * 60)


if __name__ == "__main__":
    main()