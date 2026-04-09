# Personal Stock Advisor: Nifty Stock Analyzer

A conservative, rule-based stock analysis platform built with Streamlit that analyzes NSE stocks using a hybrid technical + fundamental model. Supports multiple stock indices (Nifty 500 and Nifty Microcap 250) with intelligent scoring, explainable recommendations, and comprehensive data persistence.

**Version:** 0.5

## Key Features

### 📊 Multi-Index Support
- **Nifty 500**: Large & established companies
- **Nifty Microcap 250**: Smaller, high-growth potential stocks
- Radio button selection to switch between indices seamlessly

### 🎨 Modern UI Design
- **Compact, responsive layout** optimized for desktop and tablet viewing
- **Consistent bluish color scheme** across all buttons and interactive elements
- **Organized filter sections** with clear visual hierarchy
- **Color-coded recommendations**: 
  - 🟢 BUY (Green)
  - 🟡 HOLD (Gold)
  - 🔴 AVOID (Red)

### 🔍 Advanced Analysis Engine (50+ Indicators)
**Technical Indicators:**
- Moving Averages (EMA 5/20/50/200, SMA 10/20/50)
- Momentum: RSI (14), MACD, Stochastic, CCI
- Volatility: Bollinger Bands, ATR, Keltner Channel
- Trend: ADX, DMI, Ichimoku
- Volume: OBV, CMF, A/D Line
- Support/Resistance levels

**Fundamental Metrics:**
- Valuation: P/E, PEG, Price-to-Book, EV/EBITDA
- Profitability: ROE, ROA, Profit Margin
- Growth: Revenue Growth, Earnings Growth Rate
- Solvency: Debt-to-Equity, Current Ratio
- Yield: Dividend Yield, Payout Ratio

### 💾 Data Management
- **Refresh Data Button**: Repull latest index constituents from NSE servers
- **Reset All Button**: Clear all filters and cache to start fresh
- **Automatic Caching**: Smart caching with refresh thresholds (default 24 hours)
- **Fallback Mechanisms**: Graceful fallback to local CSV files if APIs are unavailable

### 📈 Analysis & Reporting
- **Real-time Analysis**: Run conservative scoring across selected universe
- **Load Previous Runs**: Reuse and compare past analysis results
- **Deep Dive View**: Detailed stock analysis with:
  - Technical snapshots
  - Fundamental snapshots
  - 1-year price trend chart
  - Detailed reasoning notes
- **Export Capabilities**:
  - 📄 Export to CSV
  - 📊 Export to Excel (with formatting)

### 🎯 Filtering & Selection
- Filter by sector (multiselect)
- Filter by market cap category (All, Large, Medium, Small)
- "Only BUY" checkbox to show only buy recommendations
- Stock selection via interactive dataframe with row selection
- Visual indicator of matching stock count

### ⏱️ Footer Information
- Application version display
- Last data update timestamp
- Last analysis run timestamp

## Architecture

```
┌─ UI Layer (app.py)
│  ├─ Streamlit dashboard with filters & controls
│  ├─ Interactive dataframe with multi-row selection
│  ├─ Deep analysis view modal
│  └─ Export functionality (CSV/Excel)
│
├─ Service Layer (src/advisor_service.py)
│  ├─ Analysis orchestration
│  ├─ Universe analysis execution
│  └─ Result persistence
│
├─ Analysis Engine (src/analysis.py)
│  ├─ Compute 50+ technical indicators
│  ├─ Score calculation (technical + fundamental)
│  ├─ Recommendation logic (BUY/HOLD/AVOID)
│  └─ Confidence band assignment
│
├─ Data Layer
│  ├─ MasterStockLoader (src/data_fetcher.py): Index constituents from NSE/APIs
│  ├─ YahooFinanceClient (src/data_fetcher.py): Stock data & fundamentals
│  └─ Repository (src/repository.py): Database CRUD operations
│
└─ Persistence Layer (src/db.py)
   ├─ stocks_master (index composition)
   ├─ stock_data (OHLCV history)
   ├─ fundamentals (valuation metrics)
   ├─ analysis_results (recommendation scores)
   └─ analysis_runs (run history for reuse)
```

## Project Structure

```
.
├── app.py                          # Main Streamlit application
├── init_db.py                      # Database initialization
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── data/
│   ├── nifty500_master.csv        # Nifty 500 constituents (fallback)
│   └── nifty_microcap250_master.csv # Nifty Microcap 250 constituents (fallback)
└── src/
    ├── __init__.py
    ├── advisor_service.py          # Analysis orchestration service
    ├── analysis.py                 # Core scoring & indicator logic
    ├── bootstrap.py                # Data initialization & refresh
    ├── config.py                   # Configuration constants & URLs
    ├── data_fetcher.py             # NSE & Yahoo Finance integrations
    ├── db.py                       # Database schema & migrations
    └── repository.py               # Database access layer (DAO)
```

## Setup & Installation

### Prerequisites
- Python 3.8+
- SQLite3 (usually included with Python)

### Installation

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python init_db.py

# Run the application
streamlit run app.py
```

The app will be available at `http://localhost:8501`

## Usage Guide

### 1. Select Index
- Choose between **Nifty 500** or **Nifty Microcap 250**
- Click **🔄 Refresh** to repull the latest index constituents from NSE
- Click **↺ Reset** to clear all filters and start fresh

### 2. Apply Filters
- **Sector**: Multiselect sectors relevant to your analysis
- **Market Cap**: Filter by company size (Large/Medium/Small)
- **Only BUY**: Checkbox to show only stocks with BUY recommendations

### 3. Run Analysis
- Click **Analyze** button to execute conservative scoring
- Wait for the spinner to complete (analysis runs on selected universe)

### 4. Review Results
- Interactive table displays all analyzed stocks
- Click a row to select it, then click **🔍 Deep Dive** for detailed analysis
- Use **📄 CSV** or **📊 Excel** buttons to export results

### 5. Deep Analysis View
- View technical and fundamental snapshots
- Read AI-generated reasoning notes
- Analyze 1-year price trend chart
- Click **← Back** to return to main analysis

### 6. Load Previous Runs
- Dropdown shows past analysis runs with timestamp and stock count
- Click **Load Run** to reload a previous analysis without re-running

## Scoring Methodology

The app uses a **conservative, hybrid approach** combining technical and fundamental signals:

### Score Components (~100 points max)
- **Technical Signals** (~30 points): Trend strength, momentum, volatility
- **Fundamental Signals** (~30 points): Valuation, growth, profitability
- **Volatility Assessment** (~5 points): Risk adjustment

### Recommendation Logic
- **BUY**: Score ≥ 70 (strong buy signals across multiple indicators)
- **HOLD**: Score 50-69 (mixed signals or neutral indicators)
- **AVOID**: Score < 50 (weak or negative signals)

### Confidence Bands
- **High**: Score decisiveness indicates strong conviction
- **Medium**: Mixed signals with moderate confidence
- **Low**: Weak signals or conflicting indicators

## Data Sources

- **Index Constituents**: NSE official API (niftyindices.com) with local CSV fallback
- **Historical Data**: Yahoo Finance (yfinance library)
- **Fundamentals**: Yahoo Finance API

## Technical Notes

- Stock symbols are converted to Yahoo Finance format: `{SYMBOL}.NS`
- Analysis results are cached for 24 hours by default
- Refresh thresholds apply per stock (avoids excessive API calls)
- Failed symbol analysis is gracefully skipped with error logging
- Database migrations run automatically on app startup

## Limitations & Disclaimers

⚠️ **This is an educational tool and not investment advice.**
- Use for analysis and research only
- Market conditions change; past performance ≠ future results
- Always conduct your own due diligence before investing
- Recommended to combine with other analysis tools and expert advice

## Future Enhancements

- [ ] Real-time price alerts
- [ ] Portfolio tracking & performance monitoring
- [ ] Advanced charting with custom date ranges
- [ ] Multi-user support & authentication
- [ ] API endpoint for programmatic access
- [ ] Email notifications for signals
- [ ] Sector-wise performance comparison

## License

Educational use. No warranty provided.
