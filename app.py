from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file
)

import pandas as pd
import os

import plotly.graph_objs as go
import plotly.offline as pyo

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)


# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(__name__)

app.secret_key = "student_result_analysis_secret_key"

UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ============================================================
# MULTI-USER STAFF LOGIN
# ============================================================

USERS = {
    "HOD": "HOD@123",
    "Principal": "Principal@123",
    "Professor": "Professor@123"
}

PASS_MARK = 35


# ============================================================
# LOGIN
# ============================================================

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        # Check username and password against all authorized staff accounts
        if username in USERS and USERS[username] == password:
            session["user"] = username

            return redirect(
                url_for("index")
            )

        return render_template(
            "login.html",
            error="Invalid Username or Password"
        )

    return render_template("login.html")


# ============================================================
# UPLOAD PAGE
# ============================================================

@app.route("/index", methods=["GET", "POST"])
def index():

    if "user" not in session:
        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        if "file" not in request.files:

            return render_template(
                "index.html",
                error="No file uploaded"
            )

        file = request.files["file"]

        if file.filename == "":

            return render_template(
                "index.html",
                error="No file selected"
            )

        if not file.filename.lower().endswith(".xlsx"):

            return render_template(
                "index.html",
                error="Please upload an Excel (.xlsx) file"
            )

        filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            "uploaded_data.xlsx"
        )

        try:

            file.save(filepath)

            # Validate immediately
            test_df = pd.read_excel(filepath)

            required_columns = [
                "Name",
                "USN",
                "Subject Name",
                "Subject Code",
                "Marks"
            ]

            missing_columns = [
                column
                for column in required_columns
                if column not in test_df.columns
            ]

            if missing_columns:

                os.remove(filepath)

                return render_template(
                    "index.html",
                    error=(
                        "Missing required columns: "
                        + ", ".join(missing_columns)
                    )
                )

            session["uploaded_file"] = filepath

            return redirect(
                url_for("dashboard")
            )

        except Exception as e:

            return render_template(
                "index.html",
                error=f"Error processing Excel file: {str(e)}"
            )

    return render_template("index.html")


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    filepath = session.get("uploaded_file")

    if (
        not filepath
        or not os.path.exists(filepath)
    ):
        return None

    df = pd.read_excel(filepath)

    required_columns = [
        "Name",
        "USN",
        "Subject Name",
        "Subject Code",
        "Marks"
    ]

    for column in required_columns:

        if column not in df.columns:

            raise ValueError(
                f"Missing required column: {column}"
            )

    # Clean marks
    df["Marks"] = pd.to_numeric(
        df["Marks"],
        errors="coerce"
    )

    df.dropna(
        subset=["Marks"],
        inplace=True
    )

    df["Marks"] = df["Marks"].clip(
        lower=0,
        upper=100
    )

    # Convert text columns
    df["Name"] = df["Name"].astype(str).str.strip()

    df["USN"] = df["USN"].astype(str).str.strip()

    df["Subject Name"] = (
        df["Subject Name"]
        .astype(str)
        .str.strip()
    )

    df["Subject Code"] = (
        df["Subject Code"]
        .astype(str)
        .str.strip()
    )

    return df


# ============================================================
# STUDENT ANALYSIS
# ============================================================

def create_student_analysis(df):

    records = []

    grouped = df.groupby(
        ["USN", "Name"],
        sort=False
    )

    for (usn, name), group in grouped:

        marks = group["Marks"]

        total = marks.sum()

        subject_count = len(marks)

        average = marks.mean()

        percentage = average

        failed_subjects = int(
            (marks < PASS_MARK).sum()
        )

        passed_subjects = int(
            (marks >= PASS_MARK).sum()
        )

        result = (
            "PASS"
            if failed_subjects == 0
            else "FAIL"
        )

        records.append({

            "USN": usn,

            "Name": name,

            "Subjects": subject_count,

            "Total": round(
                total,
                2
            ),

            "Average": round(
                average,
                2
            ),

            "Percentage": round(
                percentage,
                2
            ),

            "Passed Subjects":
                passed_subjects,

            "Failed Subjects":
                failed_subjects,

            "Result": result
        })

    student_df = pd.DataFrame(records)

    if not student_df.empty:

        student_df = student_df.sort_values(
            by=[
                "Percentage",
                "Total"
            ],
            ascending=False
        ).reset_index(drop=True)

        student_df["Rank"] = (
            student_df["Percentage"]
            .rank(
                method="min",
                ascending=False
            )
            .astype(int)
        )

    return student_df


# ============================================================
# PERFORMANCE CATEGORY
# ============================================================

def performance_category(value):

    if value >= 85:
        return "Excellent"

    elif value >= 70:
        return "Good"

    elif value >= 50:
        return "Average"

    elif value >= 35:
        return "Poor"

    else:
        return "Fail"


# ============================================================
# SUBJECT ANALYSIS
# ============================================================

def create_subject_analysis(df):

    records = []

    if df.empty:
        return pd.DataFrame(
            columns=[
                "Subject",
                "Average",
                "Highest",
                "Lowest",
                "Pass",
                "Fail",
                "Pass %",
                "Fail %",
                "Difficulty Score",
                "Difficulty"
            ]
        )

    for subject, group in df.groupby(
        "Subject Name"
    ):

        average = group["Marks"].mean()

        highest = group["Marks"].max()

        lowest = group["Marks"].min()

        total_students = len(group)

        pass_students = int(
            (
                group["Marks"]
                >= PASS_MARK
            ).sum()
        )

        fail_students = int(
            (
                group["Marks"]
                < PASS_MARK
            ).sum()
        )

        pass_percentage = (
            pass_students
            / total_students
            * 100
            if total_students
            else 0
        )

        fail_percentage = (
            fail_students
            / total_students
            * 100
            if total_students
            else 0
        )

        # Difficulty score
        difficulty_score = round(
            (
                (100 - average) * 0.5
                + fail_percentage * 0.5
            ),
            2
        )

        if difficulty_score >= 50:
            difficulty = "High"

        elif difficulty_score >= 30:
            difficulty = "Medium"

        else:
            difficulty = "Low"

        records.append({

            "Subject": subject,

            "Average": round(
                average,
                2
            ),

            "Highest": int(
                highest
            ),

            "Lowest": int(
                lowest
            ),

            "Pass": pass_students,

            "Fail": fail_students,

            "Pass %": round(
                pass_percentage,
                2
            ),

            "Fail %": round(
                fail_percentage,
                2
            ),

            "Difficulty Score":
                difficulty_score,

            "Difficulty":
                difficulty
        })

    return pd.DataFrame(records)


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    if "uploaded_file" not in session:

        return redirect(
            url_for("index")
        )

    try:

        df = load_data()

        if df is None:

            return redirect(
                url_for("index")
            )

        student_df = (
            create_student_analysis(df)
        )

        subject_df = (
            create_subject_analysis(df)
        )

        # ====================================================
        # FILTERS
        # ====================================================

        selected_student = request.args.get(
            "student",
            "All"
        )

        selected_subject = request.args.get(
            "subject",
            "All"
        )

        selected_result = request.args.get(
            "result",
            "All"
        )

        filtered_df = df.copy()

        # Student filter
        if selected_student != "All":

            selected_usn = (
                student_df[
                    student_df["Name"]
                    == selected_student
                ]["USN"]
                .tolist()
            )

            filtered_df = filtered_df[
                filtered_df["USN"]
                .isin(selected_usn)
            ]

        # Subject filter
        if selected_subject != "All":

            filtered_df = filtered_df[
                filtered_df["Subject Name"]
                == selected_subject
            ]

        # Result filter
        if selected_result != "All":

            result_students = (
                student_df[
                    student_df["Result"]
                    == selected_result
                ]["USN"]
            )

            filtered_df = filtered_df[
                filtered_df["USN"]
                .isin(result_students)
            ]

        # ====================================================
        # FILTERED STUDENT ANALYSIS
        # ====================================================

        filtered_student_df = (
            create_student_analysis(
                filtered_df
            )
        )

        filtered_subject_df = (
            create_subject_analysis(
                filtered_df
            )
        )

        # ====================================================
        # KPI
        # ====================================================

        total_students = len(
            filtered_student_df
        )

        total_subjects = (
            filtered_df["Subject Name"]
            .nunique()
        )

        average_marks = (
            round(
                filtered_df["Marks"].mean(),
                2
            )
            if not filtered_df.empty
            else 0
        )

        pass_students = len(
            filtered_student_df[
                filtered_student_df["Result"]
                == "PASS"
            ]
        )

        fail_students = len(
            filtered_student_df[
                filtered_student_df["Result"]
                == "FAIL"
            ]
        )

        pass_percentage = (

            round(
                pass_students
                / total_students
                * 100,
                2
            )

            if total_students
            else 0
        )

        # Topper
        topper_name = "N/A"

        topper_marks = 0

        if not filtered_student_df.empty:

            topper = (
                filtered_student_df.iloc[0]
            )

            topper_name = topper["Name"]

            topper_marks = topper["Percentage"]

        # ====================================================
        # PERFORMANCE DISTRIBUTION
        # ====================================================

        distribution = {

            "Excellent": 0,

            "Good": 0,

            "Average": 0,

            "Poor": 0,

            "Fail": 0
        }

        for value in (
            filtered_student_df["Percentage"]
        ):

            category = (
                performance_category(
                    value
                )
            )

            distribution[
                category
            ] += 1

        # ====================================================
        # PERFORMANCE CHART
        # ====================================================

        performance_fig = go.Figure(

            data=[

                go.Bar(

                    x=list(
                        distribution.keys()
                    ),

                    y=list(
                        distribution.values()
                    ),

                    text=list(
                        distribution.values()
                    ),

                    textposition="auto"
                )
            ]
        )

        performance_fig.update_layout(

            title="Student Performance Distribution",

            xaxis_title="Performance Category",

            yaxis_title="Number of Students",

            template="plotly_white"
        )

        performance_chart = pyo.plot(

            performance_fig,

            output_type="div",

            include_plotlyjs="cdn"
        )

        # ====================================================
        # PASS FAIL PIE
        # ====================================================

        pie_fig = go.Figure(

            data=[

                go.Pie(

                    labels=[
                        "Pass",
                        "Fail"
                    ],

                    values=[
                        pass_students,
                        fail_students
                    ],

                    hole=0.45
                )
            ]
        )

        pie_fig.update_layout(

            title="Overall Pass vs Fail",

            template="plotly_white"
        )

        pie_chart = pyo.plot(

            pie_fig,

            output_type="div",

            include_plotlyjs=False
        )

        # ====================================================
        # SUBJECT AVERAGE CHART
        # ====================================================

        subject_fig = go.Figure(

            data=[

                go.Bar(

                    x=filtered_subject_df[
                        "Subject"
                    ],

                    y=filtered_subject_df[
                        "Average"
                    ],

                    text=filtered_subject_df[
                        "Average"
                    ],

                    textposition="auto"
                )
            ]
        )

        subject_fig.update_layout(

            title="Average Marks by Subject",

            xaxis_title="Subject",

            yaxis_title="Average Marks",

            template="plotly_white"
        )

        subject_chart = pyo.plot(

            subject_fig,

            output_type="div",

            include_plotlyjs=False
        )

        # ====================================================
        # DIFFICULTY CHART
        # ====================================================

        difficulty_fig = go.Figure(

            data=[

                go.Bar(

                    x=filtered_subject_df[
                        "Subject"
                    ],

                    y=filtered_subject_df[
                        "Difficulty Score"
                    ],

                    text=filtered_subject_df[
                        "Difficulty"
                    ],

                    textposition="auto"
                )
            ]
        )

        difficulty_fig.update_layout(

            title="Subject Difficulty Analysis",

            xaxis_title="Subject",

            yaxis_title="Difficulty Score",

            template="plotly_white"
        )

        difficulty_chart = pyo.plot(

            difficulty_fig,

            output_type="div",

            include_plotlyjs=False
        )

        # ====================================================
        # MARKS HISTOGRAM
        # ====================================================

        histogram_fig = go.Figure(

            data=[

                go.Histogram(

                    x=filtered_df["Marks"],

                    nbinsx=10
                )
            ]
        )

        histogram_fig.update_layout(

            title="Marks Distribution",

            xaxis_title="Marks",

            yaxis_title="Students",

            template="plotly_white"
        )

        histogram_chart = pyo.plot(

            histogram_fig,

            output_type="div",

            include_plotlyjs=False
        )

        # ====================================================
        # TOP 5
        # ====================================================

        top5 = (
            filtered_student_df
            .head(5)
        )

        ranking_fig = go.Figure(

            data=[

                go.Bar(

                    x=top5["Name"],

                    y=top5["Percentage"],

                    text=top5["Percentage"],

                    textposition="auto"
                )
            ]
        )

        ranking_fig.update_layout(

            title="Top 5 Students",

            xaxis_title="Student",

            yaxis_title="Percentage",

            template="plotly_white"
        )

        ranking_chart = pyo.plot(

            ranking_fig,

            output_type="div",

            include_plotlyjs=False
        )

        # ====================================================
        # DROPDOWN DATA
        # ====================================================

        students = sorted(
            df["Name"]
            .dropna()
            .unique()
            .tolist()
        )

        subjects = sorted(
            df["Subject Name"]
            .dropna()
            .unique()
            .tolist()
        )

        # ====================================================
        # RENDER
        # ====================================================

        return render_template(

            "index.html",

            analysis=(
                filtered_subject_df
                .to_dict(
                    orient="records"
                )
            ),

            student_analysis=(
                filtered_student_df
                .to_dict(
                    orient="records"
                )
            ),

            subject_analysis=(
                filtered_subject_df
                .to_dict(
                    orient="records"
                )
            ),

            students=students,

            subjects=subjects,

            selected_student=(
                selected_student
            ),

            selected_subject=(
                selected_subject
            ),

            selected_result=(
                selected_result
            ),

            total_students=(
                total_students
            ),

            total_subjects=(
                total_subjects
            ),

            average_marks=(
                average_marks
            ),

            pass_percentage=(
                pass_percentage
            ),

            pass_students=(
                pass_students
            ),

            fail_students=(
                fail_students
            ),

            topper_name=(
                topper_name
            ),

            topper_marks=(
                topper_marks
            ),

            distribution=(
                distribution
            ),

            pie_chart=(
                pie_chart
            ),

            performance_chart=(
                performance_chart
            ),

            subject_chart=(
                subject_chart
            ),

            difficulty_chart=(
                difficulty_chart
            ),

            histogram_chart=(
                histogram_chart
            ),

            ranking_chart=(
                ranking_chart
            )
        )

    except Exception as e:

        print(
            "Dashboard Error:",
            str(e)
        )

        return render_template(

            "index.html",

            error=(
                f"Error processing Excel file: {str(e)}"
            )
        )


# ============================================================
# STUDENT PROFILE
# ============================================================

@app.route("/student/<usn>")
def student_profile(usn):

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    try:

        df = load_data()

        student_df = (
            create_student_analysis(df)
        )

        student = student_df[
            student_df["USN"] == usn
        ]

        if student.empty:

            return redirect(
                url_for("dashboard")
            )

        student = student.iloc[0]

        marks_df = df[
            df["USN"] == usn
        ].copy()

        marks_df["Status"] = (
            marks_df["Marks"]
            .apply(
                lambda x:
                "PASS"
                if x >= PASS_MARK
                else "FAIL"
            )
        )

        strongest = marks_df.loc[
            marks_df["Marks"].idxmax()
        ]

        weakest = marks_df.loc[
            marks_df["Marks"].idxmin()
        ]

        return render_template(

            "student_profile.html",

            student=student.to_dict(),

            marks=marks_df.to_dict(
                orient="records"
            ),

            strongest=strongest.to_dict(),

            weakest=weakest.to_dict()
        )

    except Exception as e:

        print(
            "Profile Error:",
            str(e)
        )

        return redirect(
            url_for("dashboard")
        )


# ============================================================
# EXCEL REPORT
# ============================================================

@app.route("/download")
def download_report():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    try:

        df = load_data()

        if df is None:

            return redirect(
                url_for("index")
            )

        student_df = (
            create_student_analysis(df)
        )

        subject_df = (
            create_subject_analysis(df)
        )

        # ====================================================
        # DISTRIBUTION
        # ====================================================

        distribution = {

            "Excellent": 0,

            "Good": 0,

            "Average": 0,

            "Poor": 0,

            "Fail": 0
        }

        for value in (
            student_df["Percentage"]
        ):

            category = (
                performance_category(
                    value
                )
            )

            distribution[
                category
            ] += 1

        distribution_df = pd.DataFrame({

            "Category":
                list(
                    distribution.keys()
                ),

            "Students":
                list(
                    distribution.values()
                )
        })

        # ====================================================
        # SUMMARY
        # ====================================================

        pass_students = len(
            student_df[
                student_df["Result"]
                == "PASS"
            ]
        )

        fail_students = len(
            student_df[
                student_df["Result"]
                == "FAIL"
            ]
        )

        pass_percentage = (

            round(
                pass_students
                / len(student_df)
                * 100,
                2
            )

            if len(student_df)
            else 0
        )

        summary_df = pd.DataFrame({

            "Metric": [

                "Total Students",

                "Total Subjects",

                "Average Marks",

                "Pass Students",

                "Fail Students",

                "Pass Percentage",

                "Topper"
            ],

            "Value": [

                len(student_df),

                df[
                    "Subject Name"
                ].nunique(),

                round(
                    df["Marks"].mean(),
                    2
                ),

                pass_students,

                fail_students,

                pass_percentage,

                (
                    student_df.iloc[0]["Name"]
                    if not student_df.empty
                    else "N/A"
                )
            ]
        })

        # ====================================================
        # EXCEL
        # ====================================================

        output = BytesIO()

        with pd.ExcelWriter(
            output,
            engine="xlsxwriter"
        ) as writer:

            df.to_excel(
                writer,
                index=False,
                sheet_name="Detailed Results"
            )

            student_df.to_excel(
                writer,
                index=False,
                sheet_name="Student Rankings"
            )

            subject_df.to_excel(
                writer,
                index=False,
                sheet_name="Subject Analysis"
            )

            distribution_df.to_excel(
                writer,
                index=False,
                sheet_name="Performance"
            )

            summary_df.to_excel(
                writer,
                index=False,
                sheet_name="Dashboard Summary"
            )

            workbook = writer.book

            header_format = (
                workbook.add_format({

                    "bold": True,

                    "font_color": "white",

                    "bg_color": "#1F4E78",

                    "border": 1,

                    "align": "center",

                    "valign": "vcenter"
                })
            )

            title_format = (
                workbook.add_format({

                    "bold": True,

                    "font_size": 14,

                    "font_color": "white",

                    "bg_color": "#0F172A",

                    "align": "center"
                })
            )

            for sheet_name, dataframe in [

                (
                    "Detailed Results",
                    df
                ),

                (
                    "Student Rankings",
                    student_df
                ),

                (
                    "Subject Analysis",
                    subject_df
                ),

                (
                    "Performance",
                    distribution_df
                ),

                (
                    "Dashboard Summary",
                    summary_df
                )
            ]:

                worksheet = writer.sheets[
                    sheet_name
                ]

                # Freeze header
                worksheet.freeze_panes(
                    1,
                    0
                )

                # Header
                for col_num, column in enumerate(
                    dataframe.columns
                ):

                    worksheet.write(
                        0,
                        col_num,
                        column,
                        header_format
                    )

                # Column widths
                for col_num, column in enumerate(
                    dataframe.columns
                ):

                    width = max(

                        len(str(column)) + 3,

                        min(

                            30,

                            dataframe[
                                column
                            ]
                            .astype(str)
                            .map(len)
                            .max()
                            + 3
                        )
                    )

                    worksheet.set_column(
                        col_num,
                        col_num,
                        width
                    )

                # Autofilter
                if not dataframe.empty:

                    worksheet.autofilter(
                        0,
                        0,
                        len(dataframe),
                        len(dataframe.columns) - 1
                    )

        output.seek(0)

        return send_file(

            output,

            download_name=(
                "Student_Result_Analysis_Report.xlsx"
            ),

            as_attachment=True,

            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

    except Exception as e:

        print(
            "Excel Report Error:",
            str(e)
        )

        return redirect(
            url_for("dashboard")
        )


# ============================================================
# PDF REPORT
# ============================================================

@app.route("/download-pdf")
def download_pdf():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    try:

        df = load_data()

        student_df = (
            create_student_analysis(df)
        )

        subject_df = (
            create_subject_analysis(df)
        )

        output = BytesIO()

        doc = SimpleDocTemplate(

            output,

            pagesize=landscape(A4),

            rightMargin=30,

            leftMargin=30,

            topMargin=30,

            bottomMargin=30
        )

        styles = (
            getSampleStyleSheet()
        )

        title_style = ParagraphStyle(

            "TitleStyle",

            parent=styles["Title"],

            alignment=TA_CENTER,

            fontSize=22,

            spaceAfter=20
        )

        heading_style = ParagraphStyle(

            "HeadingStyle",

            parent=styles["Heading2"],

            fontSize=15,

            spaceBefore=15,

            spaceAfter=10
        )

        elements = []

        # Title
        elements.append(

            Paragraph(

                "STUDENT RESULT ANALYSIS REPORT",

                title_style
            )
        )

        elements.append(

            Paragraph(

                "Student Result Analysis System",

                styles["Heading3"]
            )
        )

        elements.append(
            Spacer(1, 15)
        )

        # ====================================================
        # SUMMARY
        # ====================================================

        total_students = len(
            student_df
        )

        total_subjects = (
            df["Subject Name"]
            .nunique()
        )

        average = round(
            df["Marks"].mean(),
            2
        )

        pass_students = len(
            student_df[
                student_df["Result"]
                == "PASS"
            ]
        )

        fail_students = len(
            student_df[
                student_df["Result"]
                == "FAIL"
            ]
        )

        pass_rate = (

            round(
                pass_students
                / total_students
                * 100,
                2
            )

            if total_students
            else 0
        )

        topper = (

            student_df.iloc[0]["Name"]

            if not student_df.empty

            else "N/A"
        )

        summary_data = [

            ["Metric", "Value"],

            [
                "Total Students",
                total_students
            ],

            [
                "Total Subjects",
                total_subjects
            ],

            [
                "Average Marks",
                average
            ],

            [
                "Pass Students",
                pass_students
            ],

            [
                "Fail Students",
                fail_students
            ],

            [
                "Pass Percentage",
                f"{pass_rate}%"
            ],

            [
                "Topper",
                topper
            ]
        ]

        summary_table = Table(
            summary_data,
            colWidths=[
                200,
                200
            ]
        )

        summary_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#1F4E78"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                )
            ])
        )

        elements.append(
            summary_table
        )

        # ====================================================
        # RANKING
        # ====================================================

        elements.append(

            Paragraph(
                "Student Rankings",
                heading_style
            )
        )

        ranking_data = [

            [
                "Rank",
                "Name",
                "USN",
                "Total",
                "Average",
                "Percentage",
                "Result"
            ]
        ]

        for _, row in (
            student_df.head(20)
            .iterrows()
        ):

            ranking_data.append([

                row["Rank"],

                row["Name"],

                row["USN"],

                row["Total"],

                row["Average"],

                f'{row["Percentage"]}%',

                row["Result"]
            ])

        ranking_table = Table(
            ranking_data,
            repeatRows=1
        )

        ranking_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#1F4E78"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                )
            ])
        )

        elements.append(
            ranking_table
        )

        # ====================================================
        # SUBJECT ANALYSIS
        # ====================================================

        elements.append(

            Paragraph(
                "Subject Analysis",
                heading_style
            )
        )

        subject_data = [

            [
                "Subject",
                "Average",
                "Highest",
                "Lowest",
                "Pass %",
                "Fail %",
                "Difficulty"
            ]
        ]

        for _, row in (
            subject_df.iterrows()
        ):

            subject_data.append([

                row["Subject"],

                row["Average"],

                row["Highest"],

                row["Lowest"],

                f'{row["Pass %"]}%',

                f'{row["Fail %"]}%',

                row["Difficulty"]
            ])

        subject_table = Table(
            subject_data,
            repeatRows=1
        )

        subject_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#1F4E78"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                )
            ])
        )

        elements.append(
            subject_table
        )

        elements.append(
            Spacer(1, 20)
        )

        elements.append(

            Paragraph(

                "Generated by Student Result Analysis System",

                styles["Normal"]
            )
        )

        doc.build(elements)

        output.seek(0)

        return send_file(

            output,

            download_name=(
                "Student_Result_Analysis_Report.pdf"
            ),

            as_attachment=True,

            mimetype="application/pdf"
        )

    except Exception as e:

        print(
            "PDF Error:",
            str(e)
        )

        return redirect(
            url_for("dashboard")
        )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    os.makedirs(
        UPLOAD_FOLDER,
        exist_ok=True
    )

    app.run(
        debug=True
    )