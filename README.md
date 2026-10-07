# Amazon Sales Pulse

A creative local dashboard to analyse customers and sales, fed by a data pipeline and saved to Excel.

## Run it (Windows)
1. Install Python 3.9+ from python.org (tick "Add Python to PATH").
2. Extract the zip, double-click **run.bat**.
3. Your browser opens at http://127.0.0.1:5000

## Run it (Mac / Linux)
```
chmod +x run.sh && ./run.sh
```
Internet is needed on first load only for the Chart.js library and fonts (loaded from a CDN).

## What you get
| Tab | Contents |
|---|---|
| Overview | KPIs, category mix, top products, 30-day trend |
| Sales | Daily / Weekly / Monthly / Yearly - bar or area chart, orders line, category doughnut, units chart, table |
| Customers | Segments, new customers per month, revenue by city, top 10 customers, lifetime value, repeat rate |
| Orders & New Entry | Form that saves a new record straight into the Excel sheet, searchable order list |
| Pipeline | Animated flow, run now, **Live feed** toggle (auto-pull every N seconds), log |

All data lives in `data/sales_data.xlsx` (sheet "Orders"). You can open it in Excel, but **close it before saving new entries** - Excel locks the file. The header "Excel" button downloads a copy.

On the first run the app creates ~2.5 years of sample orders so the charts are not empty. Delete the `data` folder to regenerate.

## Live Amazon data (important)
Amazon has no public "live data" feed for customers. Real data is only available:
- **Your own seller account** through Amazon's Selling Partner API (SP-API) - supported here.
- Scraping amazon.com is against Amazon's terms and gets blocked, so it is not included.

Default is `SOURCE=demo`, which simulates a live Amazon feed so you can see the whole pipeline working.

To use your real seller account:
1. Register as an SP-API developer in Seller Central and create an app (you get Client ID, Client Secret, and a Refresh Token).
2. Edit `.env` (created automatically from `.env.example`):
   ```
   SOURCE=spapi
   LWA_CLIENT_ID=...
   LWA_CLIENT_SECRET=...
   LWA_REFRESH_TOKEN=...
   MARKETPLACE_ID=A21TJRUUN4KGV   # Amazon India
   SPAPI_ENDPOINT=https://sellingpartnerapi-eu.amazon.com
   ```
3. Restart. "Pull from Amazon" now fetches your last 2 days of orders, removes duplicates, and appends them to Excel.

Notes: Amazon hides buyer names/addresses unless your app has the restricted-data role, so customers fall back to anonymised buyer emails. The SP-API connector was written to Amazon's documented Orders API but could not be tested against a live seller account here, so expect to adjust field mapping in `pipeline.py` (`SPAPISource`) for your account.

## Files
- `app.py` Flask server and analytics API
- `pipeline.py` data sources (demo + SP-API) and the extract -> dedupe -> load step
- `storage.py` reads/writes the Excel file
- `templates/`, `static/` the dashboard UI
