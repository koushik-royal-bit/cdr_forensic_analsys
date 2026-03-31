# 🔍 CDR Forensic Analyst — AI-Powered Chatbot
An open-source, AI-assisted tool for law-enforcement investigators to analyze **Telecom Call Detail Records (CDRs)** using natural language queries — with interactive visualizations and a built-in chain-of-custody audit trail.

---

## 📁 Project Structure

```
cdr_forensics/
├── app.py               ← Main Streamlit application
├── generate_sample.py   ← Generates sample_cdr.csv
├── demo.py              ← CLI demo script (no UI needed)
├── sample_cdr.csv       ← 600-record demo dataset (auto-generated)
├── requirements.txt     ← Python dependencies
├── chain_of_custody.log ← Auto-created when queries are run
└── README.md            ← This file
```

---

## 🚀 Quick Start (5 Minutes)

### 1. Clone / Copy the project
```bash
git clone <repo-url>  # or extract the ZIP
cd cdr_forensics
```

### 2. Create a virtual environment (recommended)
```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Generate the sample dataset
```bash
python generate_sample.py
```
This creates `sample_cdr.csv` with **600 realistic CDR records** across ~45 days,
featuring 3 "suspect" numbers with elevated call activity.

### 5. Launch the app
```bash
python -m streamlit run app.py
```
Open your browser to **http://localhost:8501**

---

## 🎭 Demo Script (For Judges — No UI Required)

Run the CLI demo to see query parsing and filtering in action:

```bash
python demo.py
```

Sample output:
```
🗣️  QUERY: "Show calls from 9876543210 last month"
   Parsed → phones: ['9876543210'] | start: 2024-02-19 | end: 2024-03-21
   Results: 78 records

🗣️  QUERY: "Calls between 9876543210 and 9123456789"
   Parsed → phones: ['9876543210', '9123456789']
   Results: 247 records
```

---

## 🗣️ Natural Language Query Examples

| Query | What It Does |
|---|---|
| `Show calls from 9876543210 last week` | Filter by caller + last 7 days |
| `Calls between 9876543210 and 9123456789` | Filter calls involving both numbers |
| `All calls longer than 120 seconds last month` | Duration + date filter |
| `Calls from 9000011111 after 2024-12-01` | Caller + explicit date filter |
| `Show all calls yesterday` | All calls in the past 24h |
| `Calls from 9123456789 before 2024-06-01` | Caller + upper date bound |

---

## 📊 Features

### 🔍 Query Engine
- Extracts **phone numbers** (10–15 digit) via regex
- Parses **natural date ranges**: "last week", "last month", "yesterday", etc.
- Parses **explicit dates**: "after 2024-01-01", "before 2024-06-30"
- Parses **duration filters**: "longer than 120 seconds", "more than 2 minutes"

### 📡 Visualizations
1. **Timeline Chart** — scatter plot of calls over time (Plotly)
2. **Network Graph** — directed caller↔receiver graph (NetworkX + Plotly)
3. **Frequency Bar** — top callers by volume

### 🔒 Chain of Custody
All queries are appended to `chain_of_custody.log`:
```
2024-03-15 10:42:31 | INFO | USER="Det. Smith #4421" QUERY="Show calls from 9876543210 last week" RESULTS=14
```

### 📤 Export
- Results downloadable as CSV with one click

---

## 📋 CSV Format

Your CDR file must have these columns (case-insensitive):

```csv
caller,receiver,timestamp,duration
9876543210,9123456789,2024-03-10 14:23:00,142
9123456789,9000011111,2024-03-11 09:05:00,67
```

| Column | Type | Description |
|---|---|---|
| `caller` | string | Originating phone number |
| `receiver` | string | Receiving phone number |
| `timestamp` | datetime | Call date & time (ISO format) |
| `duration` | integer | Call duration in seconds |

---

## 🛠️ Tech Stack

| Component | Library | Version |
|---|---|---|
| Web UI | Streamlit | ≥1.32 |
| Data processing | Pandas | ≥2.0 |
| Visualizations | Plotly | ≥5.18 |
| Network graph | NetworkX | ≥3.2 |
| Numerics | NumPy | ≥1.26 |
| Query parsing | re (stdlib) | — |

**100% open-source. No paid APIs. No external services.**

---

## 🔐 Security Notes (Production Hardening)

- Make `chain_of_custody.log` append-only (`chmod 222`)
- Add authentication before deployment (e.g., Streamlit Cloud secrets)
- Encrypt the CSV uploads at rest
- Run behind HTTPS reverse proxy (nginx/Caddy)
- Sanitize phone number inputs to prevent log injection

---

## 📍 Suspect Numbers in Sample Dataset

```
9876543210  →  high call volume suspect A
9123456789  →  high call volume suspect B  
9000011111  →  high call volume suspect C
```

These three numbers have statistically elevated call frequencies compared to others in the dataset — ideal for demonstrating network analysis.

---

## 💡 Extending the Tool

- **spaCy NLP**: Replace regex parser with `en_core_web_sm` for richer entity extraction
- **Tower location**: Add `tower_id` column for geospatial mapping (Folium/Kepler.gl)
- **IMEI tracking**: Add device fingerprinting column
- **Export to PDF**: Use `reportlab` for formal evidence reports
- **REST API**: Wrap with FastAPI for integration with existing CCTNS/CIMS systems

---

*Built for law-enforcement hackathon. All data is synthetic and for demonstration only.*
