-- ============================================================
-- Month 4 — Create mirror database for DQ injection testing
-- Purpose: isolated Postgres database for injecting defects
-- Source: retaildw.warehouse  (Month 3 output — IMMUTABLE)
-- Target: retaildw_dq.warehouse (Month 4 playground)
-- ============================================================

-- Step 1: As superuser `retailco`, create the database.
-- Run from PowerShell:
-- docker exec -e PGPASSWORD=retailco month1-postgres-retail-1 \
--   psql -U retailco -d postgres -c "$(cat scripts/create_mirror_db.sql | first statement)"

CREATE DATABASE retaildw_dq
    WITH OWNER = dataeng
         ENCODING = 'UTF8'
         TEMPLATE = template0;

COMMENT ON DATABASE retaildw_dq IS
    'Month 4 Data Quality mirror of retaildw. Synthetic defects injected for GX validation testing.';


-- Step 2: Copy schema + data from retaildw to retaildw_dq.
-- Done outside SQL, via pg_dump | psql pipeline:
--
-- docker exec -e PGPASSWORD=dataeng123 month1-postgres-retail-1 bash -c \
--   "pg_dump -U dataeng -d retaildw -n warehouse --no-owner --no-privileges \
--    | psql -U dataeng -d retaildw_dq"