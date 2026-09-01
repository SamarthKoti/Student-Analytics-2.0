# 📊 Student Analytics 2.0

A web-based **Student Result Analysis System** built with **Flask, Pandas, Plotly, HTML, CSS, and Bootstrap**.

The application transforms student result data from Excel into interactive academic insights, rankings, subject analysis, performance statistics, and visual dashboards.

---

## 🚀 Features

### 🔐 Secure Login
- Multi-user staff login
- Role-based user accounts
- Session-based authentication
- Logout functionality

### 📂 Excel Result Upload
Upload student result data in `.xlsx` format and automatically process the records.

### 📊 Dashboard Analytics
The dashboard provides:

- Total number of students
- Total number of subjects
- Average marks
- Pass percentage
- Topper information
- Pass/Fail statistics

### 📚 Subject Analysis
For every subject, the system calculates:

- Average marks
- Highest marks
- Lowest marks
- Number of students passed
- Number of students failed
- Pass percentage
- Fail percentage
- Difficulty score
- Difficulty classification

### 📈 Interactive Visualizations

The system uses Plotly to provide interactive charts:

- **Student Performance Distribution**
- **Average Marks by Subject**
- **Subject Difficulty Analysis**
- **Marks Distribution**
- **Top 5 Student Ranking**
- **Pass vs Fail Analysis**

Different chart types are used to make the analysis easier to understand instead of displaying only bar charts.

### 👨‍🎓 Student Analysis

Individual student performance includes:

- Total marks
- Average marks
- Percentage
- Passed subjects
- Failed subjects
- Overall result
- Strongest subject
- Weakest subject

### 📥 Reports

Generate downloadable reports containing:

- Detailed student results
- Student rankings
- Subject analysis
- Performance distribution
- Dashboard summary

---

## 🛠️ Technologies Used

| Technology | Purpose |
|------------|---------|
| Python | Backend programming |
| Flask | Web application framework |
| Pandas | Excel/data processing |
| Plotly | Interactive visualizations |
| Bootstrap | Responsive UI |
| HTML | Web structure |
| CSS | Styling |
| ReportLab | PDF report generation |
| XlsxWriter | Excel report generation |

---

## 📁 Project Structure

```text
Student-Analytics-2.0/
│
├── app.py
├── requirements.txt
│
├── static/
│   ├── logo.png
│   └── style.css
│
├── templates/
│   ├── index.html
│   ├── login.html
│   └── student_profile.html
│
├── uploads/
│
├── .gitignore
└── README.md
