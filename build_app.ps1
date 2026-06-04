$ApiKey = Read-Host "OpenRouter API Key daalo"
$Model = "deepseek/deepseek-v4-flash"
$BaseUrl = "https://openrouter.ai/api/v1/chat/completions"
$Headers = @{"Authorization" = "Bearer $ApiKey"; "Content-Type" = "application/json"}

function Invoke-AI {
    param([string]$Prompt, [int]$Max = 4000)
    $Body = @{model=$Model; max_tokens=$Max; messages=@(@{role="system";content="Return ONLY raw Python code, no markdown, no explanation."},@{role="user";content=$Prompt})} | ConvertTo-Json -Depth 10
    $R = Invoke-WebRequest -Uri $BaseUrl -Method POST -Headers $Headers -Body $Body -UseBasicParsing
    return ($R.Content | ConvertFrom-Json).choices[0].message.content.Trim()
}

function Save {
    param([string]$Path, [string]$Content)
    $Dir = Split-Path (Join-Path (Get-Location) $Path) -Parent
    if(-not(Test-Path $Dir)){New-Item -ItemType Directory -Force -Path $Dir|Out-Null}
    Set-Content -Path (Join-Path (Get-Location) $Path) -Value $Content -Encoding UTF8
    Write-Host "OK: $Path" -ForegroundColor Green
}

Write-Host "Building with DeepSeek V4 Flash..." -ForegroundColor Cyan

Save "utils\__init__.py" ""
Save "environment.yml" "name: sf-env`nchannels:`n  - snowflake`ndependencies:`n  - streamlit`n  - altair`n  - pandas`n  - snowflake-snowpark-python"

Write-Host "Generating queries..." -ForegroundColor Yellow
Save "utils\queries.py" (Invoke-AI "Write complete utils/queries.py for Snowflake Cost Analyzer using Snowpark Session and st.cache_data(ttl=1800). Functions: get_daily_credits, get_period_comparison, get_service_type_totals, get_warehouse_summary, get_warehouse_daily_trend, get_warehouse_sizing_signals, get_top_queries_by_duration, get_top_queries_by_scan, get_spill_queries, get_poor_cache_queries, get_user_stats, get_user_activity_heatmap, get_storage_trend, get_data_freshness. Use SNOWFLAKE.ACCOUNT_USAGE views with ? bindings.")

Write-Host "Generating charts..." -ForegroundColor Yellow
Save "utils\charts.py" (Invoke-AI "Write complete utils/charts.py using Altair. Functions: credit_trend_chart, service_type_donut, warehouse_bar_chart, warehouse_trend_chart, idle_time_bar_chart, user_bar_chart, user_heatmap_chart, storage_area_chart. Colors: #29B5E8 and #1A3E6B.")

Write-Host "Generating ai_insights..." -ForegroundColor Yellow
Save "utils\ai_insights.py" (Invoke-AI "Write complete utils/ai_insights.py. Functions: detect_cortex(session), get_cortex_insight(session,page,context), build_prompt(page,context), rule_based_insight(page,context), get_query_tip(session,stats). Use SNOWFLAKE.CORTEX.COMPLETE. Never send raw SQL.")

Write-Host "Generating main app..." -ForegroundColor Yellow
Save "streamlit_app.py" (Invoke-AI "Write complete streamlit_app.py for Snowflake Cost Analyzer (Streamlit in Snowflake). get_active_session() from snowflake.snowpark.context. Sidebar: date range 30 days, credit price 3.0, account info, refresh button. Home: 4 KPI cards, credit trend chart, service donut, AI insights button.")

Write-Host "Generating pages..." -ForegroundColor Yellow
Save "pages\01_Overview.py" (Invoke-AI "Write complete pages/01_Overview.py for Snowflake Cost Analyzer. Use st.session_state. Show daily credits trend, service donut, period KPIs, data freshness, AI insights.")
Save "pages\02_Warehouse_Analysis.py" (Invoke-AI "Write complete pages/02_Warehouse_Analysis.py. 4 tabs: Summary, Daily Trend, Idle Analysis, Sizing Signals. AI insights.")
Save "pages\03_Query_Intelligence.py" (Invoke-AI "Write complete pages/03_Query_Intelligence.py. 4 tabs: Slowest, Most Scanned, Spill, Poor Cache. Row selector for query tips. Show QUERY_PREVIEW only.")
Save "pages\04_User_Analysis.py" (Invoke-AI "Write complete pages/04_User_Analysis.py. Top users chart, stats table, activity heatmap.")
Save "pages\05_Storage.py" (Invoke-AI "Write complete pages/05_Storage.py. Storage trend chart, KPIs, cost estimate.")

Save "deploy\setup.sql" "-- Run as ACCOUNTADMIN`nUSE ROLE ACCOUNTADMIN;`nCREATE ROLE IF NOT EXISTS COST_ANALYZER_ROLE;`nCREATE DATABASE IF NOT EXISTS COST_ANALYZER_DB;`nCREATE SCHEMA IF NOT EXISTS COST_ANALYZER_DB.COST_ANALYZER_SCHEMA;`nCREATE WAREHOUSE IF NOT EXISTS COST_ANALYZER_WH WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;`nGRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE COST_ANALYZER_ROLE;`nGRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE COST_ANALYZER_ROLE;`nCREATE OR REPLACE STREAMLIT COST_ANALYZER_DB.COST_ANALYZER_SCHEMA.COST_ANALYZER_APP FROM '/' MAIN_FILE = '/streamlit_app.py';`nGRANT USAGE ON STREAMLIT COST_ANALYZER_DB.COST_ANALYZER_SCHEMA.COST_ANALYZER_APP TO ROLE COST_ANALYZER_ROLE;"

Write-Host "`nDone! Run: git add . && git commit -m 'Add app' && git push" -ForegroundColor Green
