# Third-party notices

**元景.智数** (telecom-insight) is an independent, clean-room implementation.
It is **not** a fork, copy, or derivative of SQLBot or any SQLBot codebase.
Domain packs, ask pipeline, SQL guard, and UI were designed and written for this project.

This file lists major third-party dependencies and their typical open-source licenses.
License texts ship with each package; consult upstream repositories for authoritative terms.

## Backend (Python)

| Component | License (typical) | Role |
|-----------|-------------------|------|
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | HTTP API framework |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | ASGI server |
| [SQLModel](https://github.com/fastapi/sqlmodel) | MIT | ORM / models (SQLAlchemy-based) |
| [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) | MIT | Database toolkit |
| [psycopg](https://github.com/psycopg/psycopg) | LGPL-3.0 (with exceptions for client use) | PostgreSQL driver |
| [PyYAML](https://github.com/yaml/pyyaml) | MIT | Pack YAML loading |
| [Pydantic](https://github.com/pydantic/pydantic) / pydantic-settings | MIT | Settings & schemas |
| [python-jose](https://github.com/mpdavis/python-jose) | MIT | JWT auth |
| [passlib](https://passlib.readthedocs.io/) | BSD-style | Password hashing utilities |
| [httpx](https://github.com/encode/httpx) | BSD-3-Clause | HTTP client |
| [LangChain](https://github.com/langchain-ai/langchain) | MIT | LLM orchestration helpers |
| [langchain-openai](https://github.com/langchain-ai/langchain) | MIT | OpenAI-compatible LLM client |
| [sqlglot](https://github.com/tobymao/sqlglot) | MIT | SQL parse / guard |
| [pytest](https://github.com/pytest-dev/pytest) | MIT | Tests (dev) |

## Frontend (web/)

| Component | License (typical) | Role |
|-----------|-------------------|------|
| [Vue](https://github.com/vuejs/core) | MIT | UI framework |
| [Vite](https://github.com/vitejs/vite) | MIT | Dev server & bundler |
| [vue-router](https://github.com/vuejs/router) | MIT | Client routing |
| [axios](https://github.com/axios/axios) | MIT | API HTTP client |
| [ECharts](https://github.com/apache/echarts) | Apache-2.0 | Charts |
| [TypeScript](https://github.com/microsoft/TypeScript) | Apache-2.0 | Typing (dev) |
| [@vitejs/plugin-vue](https://github.com/vitejs/vite-plugin-vue) | MIT | Vue SFC support (dev) |
| [vue-tsc](https://github.com/vuejs/language-tools) | MIT | Vue type-check (dev) |

## Infrastructure

| Component | License (typical) | Role |
|-----------|-------------------|------|
| [PostgreSQL](https://www.postgresql.org/) | PostgreSQL License | Demo warehouse (Docker image) |
| [Nginx](https://nginx.org/) | BSD-2-Clause | Static web serving (Docker) |

## Project license

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
Copyright 2026 元景.智数 contributors (zhouxd1).
