

.env

.env.example

.gitignore

app.py

auth_store.py

insights.py

README.md

requirements.txt
I want you to provide me  an Excel file which can challenge my features at a greater extent. So, go through my files and create a suitable Excel file of 200 students of Computer Science Engineering, where the USN starts from 2VD23CS001 to 2VD23CS200 and roll number starts from 0 to 200. I want to make the Excel file more fun by adding my friends' names. So, the friends' names are as follows: Piyoosha Tamburkar, Anusha Menasinkai, Priya Pavali, Pranjali S, Suraj Vibhuti, Vivek Pattankudi, Sagar Kushalapur, Tejas wajve, Samiksha Naikwad, Akshay Bulbule. These are my friends. I want them to be the top performers in the list of Excel file with good academic marks. I want you to add the Computer Science core subjects. The subject names should be DSA, DBMS, Computer Networks, Java Programming, Software Engineering and Project Management, and OS. These are the six subjects, and I want you to take the subject codes from the VTU portal 2022 scheme as per to the respective subjects names which I told you. Okay, now prepare a perfect Excel file for my project.

…
1:45 AM

Worked for 7m 31s
Created Student_Analytics_CSE_200.xlsx with 200 CSE students and 1,200 upload-ready result rows.

All ten friends are the top ten performers.
VTU 2022 course codes are included and documented in the workbook’s Course Reference tab, based on the official CSE scheme.
It includes varied scores, 20 students with at least one failing subject, and realistic edge cases for stronger feature testing.
Roll numbers run 0–199: that gives exactly 200 unique students; 0–200 would be 201 numbers.
Student_Analytics_CSE_200.xlsx
Spreadsheet · XLSX
1:52 AM
and also add me as top scorrer i forget to mention Samarth koti

1:57 AM

Worked for 2m 10s
Updated Student_Analytics_CSE_200.xlsx.

Samarth Koti is now the #1 scorer with 100 in all six subjects, assigned USN 2VD23CS011 and roll number 10. The file still contains exactly 200 students and 1,200 result records.

Student_Analytics_CSE_200.xlsx
Spreadsheet · XLSX
1:59 AM
provide me read me for my project so i can post it in my github account and also add the given excel sheet link in that read me so any user can access it

2:05 AM

Worked for 1m 56s
Prepared a GitHub-ready package:

README.md
Sample Excel dataset
Upload README.md to your repository root and keep the Excel file in sample-data/. The README’s download link will then work for every GitHub visitor. Replace <your-username> in the clone command with your GitHub username.

Student_Analytics_CSE_200.xlsx
Spreadsheet · XLSX

Edited README.md
+125
-0
2:07 AM




Outputs

Sources

.env

.env.example

.gitignore

View all
outputs/github_package/README.md
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
├── insights.py
├── requirements.txt
├── .env.example
├── sample-data/
│   └── Student_Analytics_CSE_200.xlsx
├── static/
├── templates/
├── data/
└── README.md
```

## Sample data reference

The sample workbook uses the following VTU 2022 Scheme course codes for Computer Science Engineering:

| Project label | Subject code | Official VTU course title |
| --- | --- | --- |
| DSA | BCS304 | Data Structures and Applications |
| DBMS | BCS403 | Database Management Systems |
| Computer Networks | BCS502 | Computer Networks |
| Java Programming | BCS306A | Object Oriented Programming with Java |
| Software Engineering and Project Management | BCS501 | Software Engineering & Project Management |
| OS | BCS303 | Operating Systems |

Course codes are based on the [VTU 2022 Scheme for B.E. Computer Science and Engineering](https://vtu.ac.in/pdf/2022_3to8/38csesch.pdf).

## Security note

Before deploying publicly, change the built-in staff credentials in `app.py`, use a strong Flask secret key, configure SMTP through environment variables, and keep `.env` out of version control.
