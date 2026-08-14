# Phase 1b — Multi-DB verification matrix (P0)

Automated coverage in CI is **URL/unit** for every P0 `db_type` (`tests/test_multi_db_urls.py`). Live connection tests are documented below; optional drivers (Hive JDBC, Dameng `dmPython`) are not required for the default `pytest` suite.

| db_type | protocol_family | driver package | unit URL test | connection test notes |
|---------|-----------------|----------------|---------------|------------------------|
| `postgres` | `postgres` | `psycopg[binary]` | ✓ `postgresql+psycopg://` | **Docker**: Compose demo DB (`docker/docker-compose.yml`); seed default datasource. Ask / test-connection against this path. |
| `mysql` | `mysql` | `pymysql` | ✓ `mysql+pymysql://` | **Docker/manual**: run a MySQL 8 container, register datasource in UI/API, `POST .../test`. Optional env-gated connector smoke if added. |
| `sqlserver` | `mssql` | `pyodbc` (+ ODBC Driver 18) | ✓ `mssql+pyodbc://` + `Driver=` | URL-unit ✓; optional driver smoke / manual host. Skip in CI if ODBC not installed. |
| `hive` | `hive` | optional Hive JDBC / PyHive stack | ✓ `hive://` | URL-unit ✓; **manual** HiveServer2 or JDBC via `extra_json`. Driver optional — skip live connect without cluster. |
| `opengauss` | `postgres` | `psycopg[binary]` | ✓ same PG scheme | URL-unit ✓; optional driver smoke against OpenGauss host. |
| `gaussdb` | `postgres` | `psycopg[binary]` | ✓ same PG scheme | URL-unit ✓; optional driver smoke against GaussDB host. |
| `oceanbase_mysql` | `mysql` | `pymysql` | ✓ same MySQL scheme | URL-unit ✓; optional driver smoke (OceanBase MySQL mode). |
| `tidb` | `mysql` | `pymysql` | ✓ same MySQL scheme | URL-unit ✓; optional driver smoke against TiDB. |
| `kingbase` | `postgres` | `psycopg[binary]` | ✓ same PG scheme | URL-unit ✓; optional driver smoke against Kingbase. |
| `dameng` | `dm` | optional `dmPython` | ✓ `dm+dmPython://` | URL-unit ✓; optional vendor driver smoke. Skip live connect without Dameng client. |

## How to verify core paths

### Postgres (Compose)

```bash
docker compose -f docker/docker-compose.yml up --build
# login demo / demo123 → default workspace → Ask on seeded Postgres datasource
```

### MySQL

1. Start MySQL (Docker example: `mysql:8` on `3306`).
2. Create a workspace datasource with `db_type=mysql`.
3. Call `POST /admin/datasources/{id}/test` with `Authorization` + `X-Workspace-Id`.

### Hive

1. Point host/port at HiveServer2 (or put JDBC params in `extra_json`).
2. Install optional Hive/JDBC client libraries locally.
3. Test connection from the datasources admin page; CI remains URL-only without a cluster.

## P1 placeholder

`gbase` / `shentong` / `polardb` / `tdsql` are UI placeholders only — not in this matrix; cannot be set as execution default.
