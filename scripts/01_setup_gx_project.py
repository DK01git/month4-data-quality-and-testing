"""
Month 4 — Step 2.1: Initialize Great Expectations project.

Creates the GX filesystem context in ./gx/ and registers the
retaildw_dq PostgreSQL data source, 5 table assets, and batch
definitions for each table.

Run once. Idempotent — re-running will recreate the same config.

Run from:  C:\\de-training\\month4
Command:   python scripts/01_setup_gx_project.py
"""

from pathlib import Path

import great_expectations as gx


# ----------------------------------------------------------------
# Constants
# ----------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # C:\de-training\month4
GX_ROOT = PROJECT_ROOT / "gx"

# Connection string for retaildw_dq (the DIRTY MIRROR, not the source)
CONNECTION_STRING = (
    "postgresql+psycopg2://dataeng:dataeng123@localhost:5432/retaildw_dq"
)

DATASOURCE_NAME = "retail_warehouse_dq"

# The 5 tables in scope for Month 4 validation
TABLES = [
    "dim_customer",
    "dim_date",
    "dim_product",
    "dim_store",
    "fact_sales",
]
SCHEMA = "warehouse"


# ----------------------------------------------------------------
# Main setup
# ----------------------------------------------------------------

def main() -> None:
    print(f"Initializing GX filesystem context at: {GX_ROOT}")

    # get_context() with a project_root_dir creates or opens a
    # Filesystem context. The gx/ folder is created if missing.
    context = gx.get_context(
        mode="file",
        project_root_dir=str(PROJECT_ROOT),
    )
    print(f"  -> Context type: {type(context).__name__}")

    # ---------- Register data source ----------
    print(f"\nRegistering data source: {DATASOURCE_NAME}")

    # Idempotent pattern: try to fetch, fall back to create.
    try:
        datasource = context.data_sources.get(DATASOURCE_NAME)
        print("  -> Data source already exists; reusing.")
    except (KeyError, ValueError):
        datasource = context.data_sources.add_postgres(
            name=DATASOURCE_NAME,
            connection_string=CONNECTION_STRING,
        )
        print("  -> Data source created.")

    # ---------- Register table assets ----------
    print(f"\nRegistering {len(TABLES)} table assets in schema '{SCHEMA}'")

    for table_name in TABLES:
        try:
            asset = datasource.get_asset(table_name)
            print(f"  -> Asset '{table_name}' already exists; reusing.")
        except (KeyError, LookupError):
            asset = datasource.add_table_asset(
                name=table_name,
                table_name=table_name,
                schema_name=SCHEMA,
            )
            print(f"  -> Asset '{table_name}' created.")

        # ---------- Batch definition (whole-table) ----------
        batch_def_name = f"{table_name}_whole_table"
        try:
            asset.get_batch_definition(batch_def_name)
            print(f"     Batch def '{batch_def_name}' already exists; reusing.")
        except (KeyError, LookupError):
            asset.add_batch_definition_whole_table(name=batch_def_name)
            print(f"     Batch def '{batch_def_name}' created.")

    # ---------- Final summary ----------
    print("\n" + "=" * 60)
    print("GX project initialization complete.")
    print("=" * 60)
    print(f"Project root: {PROJECT_ROOT}")
    print(f"GX root:      {GX_ROOT}")
    print(f"Data source:  {DATASOURCE_NAME}")
    print(f"Assets:       {', '.join(TABLES)}")
    print("\nNext step: add expectations to each table's suite (Step 3).")


if __name__ == "__main__":
    main()