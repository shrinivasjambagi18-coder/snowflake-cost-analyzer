-- =============================================================================
-- Snowflake Cost Analyzer — Native App Setup Script
-- This script runs automatically when a consumer installs the app.
-- =============================================================================

-- Application role (consumers grant privileges to this role)
CREATE APPLICATION ROLE IF NOT EXISTS COST_ANALYZER_ROLE;

-- Schema to hold app objects
CREATE SCHEMA IF NOT EXISTS COST_ANALYZER_SCHEMA;

-- Register the Streamlit app
CREATE OR REPLACE STREAMLIT COST_ANALYZER_SCHEMA.COST_ANALYZER_APP
    FROM '/'
    MAIN_FILE = '/streamlit_app.py';

-- Grant app role access to the schema and Streamlit object
GRANT USAGE ON SCHEMA COST_ANALYZER_SCHEMA
    TO APPLICATION ROLE COST_ANALYZER_ROLE;

GRANT USAGE ON STREAMLIT COST_ANALYZER_SCHEMA.COST_ANALYZER_APP
    TO APPLICATION ROLE COST_ANALYZER_ROLE;
