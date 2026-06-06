# ❄️ Snowflake Cost Analyzer

> AI-powered cost analytics for Snowflake — built as a **Streamlit in Snowflake (SiS)** app and packaged as a **Native App** for Marketplace distribution.

[![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?logo=snowflake&logoColor=white)](https://www.snowflake.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)](https://www.python.org/)

---

## 📋 Overview

Snowflake Cost Analyzer reads directly from `SNOWFLAKE.ACCOUNT_USAGE` views to provide real-time visibility into compute, storage, and query costs. It combines interactive dashboards with AI-generated insights powered by **Snowflake Cortex**.

### ✨ Key Features

- 📊 **5 interactive dashboards** — Overview, Warehouse, Queries, Users, Storage
- 🤖 **AI Insights** via `SNOWFLAKE.CORTEX.COMPLETE` (with rule-based fallback)
- 🔍 **Query optimization tips** — per-query, based on performance stats only (no raw SQL)
- 💰 **Cost projections** — period-over-period KPIs and dollar estimates
- ⚠️ **Warehouse sizing signals** — `OVERLOADED` / `OVER_PROVISIONED` / `BALANCED`
- 🛡️ **Secure by design** — no raw `QUERY_TEXT` ever sent to the LLM

---

## 🏗️ Project Structure

```
snowflake-cost-analyzer/
├── README.md
├── CLAUDE.md                       # Build instructions for Claude Code
├── environment.yml                 # Conda dependencies
├── snowflake.yml                   # Snowflake CLI connection
├── streamlit_app.py                # Main app entry point
├── pages/
│   ├── 01_Overview.py
│   ├── 02_Warehouse_Analysis.py
│   ├── 03_Query_Intelligence.py
│   ├── 04_User_Analysis.py
│   └── 05_Storage.py
├── utils/
│   ├── __init__.py
│   ├── queries.py                  # Snowpark data fetchers (cached)
│   ├── charts.py                   # Altair chart builders
│   └── ai_insights.py              # Cortex AI + rule-based fallback
└── deploy/
    ├── setup.sql                   # SiS deployment
    └── native_app/
        ├── manifest.yml
        └── setup.sql
```

---

## ✅ Prerequisites

| Requirement | Notes |
|-------------|-------|
| Snowflake account | Enterprise Edition or higher (for full `ACCOUNT_USAGE`) |
| ACCOUNTADMIN role | For initial setup |
| Snowflake CLI | `pip install snowflake-cli-labs` or download from Snowflake |
| Python 3.11+ | For local development / testing |
| `git` | For cloning the repo |

Verify tools:
```bash
snow --version
python --version
git --version
```

---

## 🚀 Quick Start — Clone & Deploy to Snowflake

### 1. Clone the repository

```bash
git clone https://github.com/shrinivasjambagi18-coder/snowflake-cost-analyzer.git
cd snowflake-cost-analyzer
```

### 2. Configure Snowflake CLI connection

```bash
snow connection add \
  --connection-name cost-analyzer-dev \
  --account <YOUR_ACCOUNT_IDENTIFIER> \
  --user <YOUR_USERNAME> \
  --role COST_ANALYZER_ROLE \
  --warehouse COST_ANALYZER_WH \
  --database COST_ANALYZER_DB \
  --schema COST_ANALYZER_SCHEMA
```

### 3. Run the setup SQL (as ACCOUNTADMIN)

This creates the database, schema, warehouse, role, and required grants.

```bash
snow sql -f deploy/setup.sql
```

### 4. Deploy the Streamlit app to SiS

```bash
snow streamlit deploy \
  --connection cost-analyzer-dev \
  --database COST_ANALYZER_DB \
  --schema COST_ANALYZER_SCHEMA \
  --warehouse COST_ANALYZER_WH \
  --open
```

The app will open in Snowsight automatically.

---

## 📦 Native App Packaging (Marketplace)

To package and submit to the Snowflake Marketplace:

### 1. Create provider-side objects

```sql
USE ROLE ACCOUNTADMIN;

CREATE DATABASE IF NOT EXISTS COST_ANALYZER_PROVIDER_DB;
CREATE SCHEMA IF NOT EXISTS COST_ANALYZER_PROVIDER_DB.APP_CODE;

CREATE STAGE IF NOT EXISTS COST_ANALYZER_PROVIDER_DB.APP_CODE.APP_STAGE
    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE');

CREATE APPLICATION PACKAGE IF NOT EXISTS COST_ANALYZER_PKG;
```

### 2. Upload source files to stage

```bash
snow stage copy . @COST_ANALYZER_PROVIDER_DB.APP_CODE.APP_STAGE \
  --connection cost-analyzer-dev \
  --recursive \
  --overwrite
```

### 3. Register version and release directive

```sql
ALTER APPLICATION PACKAGE COST_ANALYZER_PKG
    ADD VERSION v1_0
    USING '@COST_ANALYZER_PROVIDER_DB.APP_CODE.APP_STAGE'
    LABEL = '1.0.0';

ALTER APPLICATION PACKAGE COST_ANALYZER_PKG
    SET DEFAULT RELEASE DIRECTIVE
    VERSION = v1_0
    PATCH = 0;
```

### 4. Local install test

```sql
CREATE APPLICATION COST_ANALYZER_TEST
    FROM APPLICATION PACKAGE COST_ANALYZER_PKG
    USING VERSION v1_0;

GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE
    TO APPLICATION COST_ANALYZER_TEST;

GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER
    TO APPLICATION COST_ANALYZER_TEST;
```

### 5. Submit to Snowflake Marketplace

Open **Snowsight → Data Products → Provider Studio → + Listing** and follow the on-screen steps. Required:

- ≥ 5 screenshots (1280×800 minimum)
- Listing title: `Snowflake Cost Analyzer`
- Categories: `Business Intelligence`, `Analytics`, `Cost Management`
- Pricing: `Free`
- Target regions: all commercial regions

---

## 🛡️ Security

| Practice | Implementation |
|----------|----------------|
| **No raw SQL in LLM prompts** | Only pre-aggregated stats passed to Cortex |
| **Parameterized queries** | All SQL uses `?` bindings (no f-string interpolation) |
| **Read-only app** | Zero write operations to any Snowflake object |
| **Principle of least privilege** | Dedicated `COST_ANALYZER_ROLE` |
| **Graceful degradation** | Rule-based insights when Cortex is unavailable |

---

## 🧪 Local Development

```bash
# Create conda env
conda env create -f environment.yml
conda activate sf-env

# Quick syntax check
python -m py_compile streamlit_app.py pages/*.py utils/*.py
```

> ⚠️ The app must run **inside Snowflake** (`snow streamlit deploy`). It uses `get_active_session()` which is only available in the SiS runtime.

---

## 📊 App Pages

| Page | Purpose |
|------|---------|
| **Overview** | Period-over-period KPIs, daily spend trend, service-type donut |
| **Warehouse Analysis** | Credit breakdown, idle time, sizing signals (BALANCED/OVERLOADED/OVER_PROVISIONED) |
| **Query Intelligence** | Slowest, biggest, spilling, and cache-miss queries with per-query AI tips |
| **User Analysis** | Top users by query count, day-of-week × hour heatmap |
| **Storage** | Storage trend, table/stage/failsafe breakdown, monthly cost estimate |

---

## 🐛 Troubleshooting

| Error | Fix |
|-------|-----|
| `Object 'SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY' does not exist` | `GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE COST_ANALYZER_ROLE;` |
| `Failed to initialize Snowflake session` | App must run in SiS — use `snow streamlit deploy` |
| `SNOWFLAKE.CORTEX.COMPLETE is not available` | Grant `DATABASE ROLE SNOWFLAKE.CORTEX_USER`; app will fall back to rule-based insights |
| Charts render blank | Verify date range has data; Account Usage has up to 3-hour latency |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/awesome-thing`)
3. Commit your changes (`git commit -m 'Add awesome thing'`)
4. Push to the branch (`git push origin feature/awesome-thing`)
5. Open a Pull Request

---

## 📬 Support

For issues or questions, open a [GitHub Issue](https://github.com/shrinivasjambagi18-coder/snowflake-cost-analyzer/issues).
