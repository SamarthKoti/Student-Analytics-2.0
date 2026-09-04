# Student Analytics 2.0

Student Analytics 2.0 is a Flask web application for turning student-result workbooks into clear academic insights. Upload an Excel file, map its columns if needed, and explore rankings, subject performance, pass/fail trends, student profiles, and downloadable reports.

## Sample dataset

[Download the 200-student Computer Science Engineering sample workbook](sample-data/Student_Analytics_CSE_200.xlsx)

The sample has 1,200 result records: 200 students, six Computer Science Engineering subjects, marks from 0 to 100, and a variety of performance patterns for testing the dashboard and Insights hub. It includes the required data columns plus an optional `Roll Number` column.

## Features

- Staff login, account signup, and email OTP verification
- Excel `.xlsx` uploads with a column-mapping screen for differently named input files
- Student totals, averages, percentages, rankings, strongest subjects, and weakest subjects
- Subject-wise averages, marks ranges, pass/fail counts, pass rate, and difficulty indicators
- Interactive charts for performance distribution, marks distribution, subject comparisons, rankings, and pass/fail results
- Individual student profiles with per-subject results
- Downloads for detailed Excel reports, PDF reports, and backlog reports
- Insights hub with counseling priorities, failure-chain analysis, anomaly checks, batch comparison, and shareable student cards

## Required Excel columns

The application requires these headers in the uploaded workbook:

| Column | Description |
| --- | --- |
| `Name` | Student name |
| `USN` | Unique student number |
| `Subject Name` | Course or subject name |
| `Subject Code` | Course code |
| `Marks` | Numeric marks from 0 to 100 |

Any extra column, such as `Roll Number`, is allowed and can be ignored during column mapping. The default pass mark in the application is 35.

## Quick start

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/Student-Analytics-2.0.git
cd Student-Analytics-2.0
```

### 2. Create and activate a virtual environment

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure email OTP (optional for local development)

Copy the example configuration and add valid SMTP details if you want OTP codes sent by email.

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

When SMTP is not configured, the application uses a local development fallback and shows the OTP in the application output.

### 5. Run the application

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## Project structure

```text
Student-Analytics-2.0/
├── app.py
├── auth_store.py
