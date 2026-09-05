# Student Analytics 2.0

Student Analytics 2.0 is a Flask-based web application that converts student-result Excel files into meaningful academic insights. It helps faculty and academic coordinators analyze performance, identify students needing support, review subject-wise trends, and generate reports.

## About the project

Managing student marks manually through spreadsheets can be time-consuming and difficult to interpret. This project provides an interactive dashboard that processes uploaded Excel result files and presents the data through rankings, performance statistics, charts, subject analysis, and student profiles.

The application is useful for departments, faculty members, and academic coordinators who want to make data-driven academic decisions.

## Sample dataset

[Download the 200-student Computer Science Engineering sample workbook](sample-data/Student_Analytics_CSE_200.xlsx)

The sample dataset contains:

- 200 Computer Science Engineering students
- 1,200 result records
- Six core Computer Science subjects
- Marks from 0 to 100
- High performers, average performers, students with backlogs, and varied marks patterns
- Samarth Koti as the highest scorer
- Named friends as leading performers

The dataset is designed to test rankings, pass/fail analysis, subject difficulty, counseling priorities, anomaly detection, and visual reports.

## Features

- Staff login and account signup
- Email OTP verification for registration
- Excel `.xlsx` result upload
- Column mapping for files with different header names
- Student ranking and topper identification
- Student performance analysis
- Subject-wise performance analysis
- Pass/fail statistics
- Interactive Plotly charts
- Individual student profiles
- Downloadable Excel and PDF reports
- Backlog reports
- Counseling priority queue
- Failure-chain analysis
- Data anomaly detection
- Batch comparison
- Shareable student result cards

## How it works

1. A staff member logs in to the application.
2. An Excel result file is uploaded.
3. The application validates the file and maps columns when necessary.
4. Student and subject-level metrics are calculated.
5. The dashboard displays charts, rankings, performance summaries, and insights.
6. Staff can download reports or review individual student profiles.

## Analytics included

### Student-level analysis

For every student, the application calculates:

- Total marks
- Average marks
- Percentage
- Rank
- Passed subjects
- Failed subjects
- Overall result
- Strongest subject
- Weakest subject

### Subject-level analysis

For every subject, the application calculates:

- Average marks
- Highest marks
- Lowest marks
- Number of passed students
- Number of failed students
- Pass percentage
- Fail percentage
- Difficulty score
- Difficulty classification

### Insights hub

The Insights hub provides advanced academic analysis:

- Counseling queue for at-risk students
- Backlog summary by subject
- Failure-chain analysis
- Marks anomaly detection
- Batch comparison
- Student improvement and decline tracking
- Shareable student report cards

## Required Excel columns

The uploaded Excel file must contain these columns:

| Column | Description |
| --- | --- |
| `Name` | Student name |
| `USN` | Unique student number |
| `Subject Name` | Name of the subject |
| `Subject Code` | Subject code |
| `Marks` | Numeric marks between 0 and 100 |

Additional columns such as `Roll Number` are allowed. The default pass mark in the application is 35.

## Sample dataset subjects

| Subject | Subject Code | Official VTU Course Title |
| --- | --- | --- |
| DSA | BCS304 | Data Structures and Applications |
| DBMS | BCS403 | Database Management Systems |
| Computer Networks | BCS502 | Computer Networks |
| Java Programming | BCS306A | Object Oriented Programming with Java |
| Software Engineering and Project Management | BCS501 | Software Engineering & Project Management |
| OS | BCS303 | Operating Systems |

The course codes follow the [VTU 2022 Scheme for B.E. Computer Science and Engineering](https://vtu.ac.in/pdf/2022_3to8/38csesch.pdf).

## Technology stack

| Technology | Purpose |
| --- | --- |
| Python | Backend programming |
| Flask | Web framework |
| Pandas | Excel data processing |
| Plotly | Interactive charts and visualizations |
| Bootstrap | Responsive user interface |
| OpenPyXL | Excel file handling |
| XlsxWriter | Excel report generation |
| ReportLab | PDF report generation |
| QRCode | Shareable report-card QR codes |

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/Student-Analytics-2.0.git
cd Student-Analytics-2.0
```

Replace `<your-username>` with your GitHub username.

### 2. Create a virtual environment

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure email OTP

Copy the example environment file:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Update `.env` (and add the same values to Render's environment variables) to
send OTP verification emails through Brevo.

```env
BREVO_API_KEY=xkeysib-your-brevo-api-key
BREVO_FROM_EMAIL=yourgmail@gmail.com
BREVO_FROM_NAME=StudentAnalytics
```

In Brevo, add `BREVO_FROM_EMAIL` as a Sender and enter the verification code
sent to that inbox before deploying. The free plan is suitable for low-volume
project OTPs. If Brevo is not configured, the application uses a local
development fallback for OTP verification.

### 5. Run the application

```bash
python app.py
```

Open the application in your browser:

```text
http://127.0.0.1:5000
```

## Project structure

```text
Student-Analytics-2.0/
├── app.py
├── auth_store.py
├── insights.py
├── requirements.txt
├── .env.example
├── sample-data/
│   └── Student_Analytics_CSE_200.xlsx
├── static/
├── templates/
├── data/
├── uploads/
└── README.md
```

## Security note

Before deploying the project publicly:

- Change the built-in staff credentials in `app.py`
- Use a strong Flask secret key
- Configure Brevo credentials through environment variables
- Never upload the `.env` file to GitHub
- Keep user registration data private


## 🔗Live Project
    **Link:** [View Student Analytics 2.0](https://student-analytics-2-0.onrender.)

    🌐 **Live Demo:** [Explore Student Analytics 2.0](https://student-analytics-2-0.onrender.com)

## Author

Samarth Koti
