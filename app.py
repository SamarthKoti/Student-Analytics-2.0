from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file
)

from datetime import datetime, timedelta, timezone
import re

import pandas as pd
import os

import auth_store
import insights

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


def empty_dashboard_context(**overrides):
    """Defaults so index.html can render before any Excel file is analyzed."""

    context = {
        "analysis": [],
        "student_analysis": [],
        "subject_analysis": [],
        "students": [],
        "subjects": [],
        "selected_student": "All",
        "selected_subject": "All",
        "selected_result": "All",
        "total_students": 0,
        "total_subjects": 0,
        "average_marks": 0,
        "pass_percentage": 0,
        "pass_students": 0,
        "fail_students": 0,
        "topper_name": "N/A",
        "topper_marks": 0,
        "at_risk_count": 0,
        "at_risk_students": [],
        "distribution": {},
        "pie_chart": None,
        "performance_chart": None,
        "subject_chart": None,
        "difficulty_chart": None,
        "histogram_chart": None,
        "ranking_chart": None,
        "heatmap_chart": None,
        "trend_chart": None,
        "radar_chart": None,
        "error": None,
    }

    context.update(overrides)
    return context


def normalize_text(value):
    """Turn Excel cells into clean strings (avoids USN becoming '123.0')."""

    if pd.isna(value):
        return ""

    if isinstance(value, bool):
        return str(value).strip()

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value).strip()

    if isinstance(value, int):
        return str(value)

    text = str(value).strip()

    if text.lower() in {"nan", "none", "nat"}:
        return ""

    if text.endswith(".0") and text[:-2].lstrip("-").isdigit():
        return text[:-2]

    return text


# ============================================================
# PLOTLY DASHBOARD THEME
# ============================================================

CHART_FONT = "Inter, Segoe UI, Arial"

CHART_BASE = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",

    "font": {
        "family": CHART_FONT,
        "color": "#f8fafc",
        "size": 11
    },

    "margin": {
        "l": 42,
        "r": 24,
        "t": 48,
        "b": 38
    },

    "title_font": {
        "color": "#ffffff",
        "size": 14
    },

    "xaxis": {
        "color": "#cbd5e1",
        "gridcolor": "rgba(148,163,184,0.10)",
        "zerolinecolor": "rgba(148,163,184,0.18)",
        "tickfont": {
            "color": "#cbd5e1",
            "size": 10
        },
        "title_font": {
            "color": "#e2e8f0",
            "size": 10
        }
    },

    "yaxis": {
        "color": "#cbd5e1",
        "gridcolor": "rgba(148,163,184,0.10)",
        "zerolinecolor": "rgba(148,163,184,0.18)",
        "tickfont": {
            "color": "#cbd5e1",
            "size": 10
        },
        "title_font": {
            "color": "#e2e8f0",
            "size": 10
        }
    },

    "hoverlabel": {
        "bgcolor": "#111827",
        "font": {
            "color": "#ffffff"
        }
    }
}


# ============================================================
# HELPER
# ============================================================

def get_chart_layout(**kwargs):
    """
    Safely create a Plotly layout without duplicate keyword
    arguments such as legend/xaxis/yaxis.
    """

    layout = CHART_BASE.copy()

    for key, value in kwargs.items():
        layout[key] = value

    return layout


def valid_login(username, password):
    if username in USERS and USERS[username] == password:
        return True

    return auth_store.verify_registered_user(username, password)


def signup_pending():
    pending = session.get("signup")

    if not isinstance(pending, dict):
        return None

    expires_at = pending.get("expires_at")

    try:
        expiry = datetime.fromisoformat(expires_at)
    except (TypeError, ValueError):
        session.pop("signup", None)
        return None

    if datetime.now(timezone.utc) > expiry:
        session.pop("signup", None)
        return None

    if not pending.get("email"):
        session.pop("signup", None)
        return None

    return pending


def start_signup_otp(email):
    store = auth_store.load_users()

    if auth_store.find_user(store, email=email):
        return None, "This email is already registered. Please login."

    code = auth_store.generate_otp()

    try:
        delivery, preview = auth_store.deliver_otp(email, code)
    except Exception as exc:
        print(f"[StudentAnalytics OTP] send failed: {exc}")
        if isinstance(exc, RuntimeError) and str(exc).strip():
            return None, str(exc)
        return None, "Could not send the verification code. Check your Resend settings."

    session["signup"] = {
        "email": email,
        "otp_hash": auth_store.hash_otp(code),
        "expires_at": (
            datetime.now(timezone.utc)
            + timedelta(seconds=auth_store.OTP_TTL_SECONDS)
        ).isoformat(),
        "attempts": 0,
        "verified": False,
        "delivery": delivery,
        "otp_preview": preview,
    }

    return preview, None


# ============================================================
# LOGIN
# ============================================================

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = (request.form.get("username") or "").strip()
        password = request.form.get("password")

        if valid_login(username, password):

            session.clear()
            session["user"] = username

            return redirect(
                url_for("index")
            )

        return render_template(
            "login.html",
            error="Invalid Username or Password"
        )

    return render_template(
        "login.html",
        success=request.args.get("registered")
    )


# ============================================================
# SIGN UP
# ============================================================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "GET":
        session.pop("signup", None)

        return render_template(
            "signup.html",
            step="contact"
        )

    email, error = auth_store.validate_email(request.form.get("email"))

    if error:
        return render_template(
            "signup.html",
            step="contact",
            email=request.form.get("email", ""),
            error=error
        )

    preview, error = start_signup_otp(email)

    if error:
        return render_template(
            "signup.html",
            step="contact",
            email=request.form.get("email", ""),
            error=error
        )

    return render_template(
        "signup.html",
        step="otp",
        contact=email,
        otp_preview=preview,
        info="Enter the 6-digit code we sent you."
    )


@app.route("/signup/verify", methods=["POST"])
def signup_verify():

    pending = signup_pending()

    if not pending:
        return render_template(
            "signup.html",
            step="contact",
            error="Your verification session expired. Please request a new code."
        )

    code = re.sub(r"\D", "", request.form.get("otp") or "")
    pending["attempts"] = int(pending.get("attempts") or 0) + 1
    session["signup"] = pending

    if pending["attempts"] > auth_store.OTP_MAX_ATTEMPTS:
        session.pop("signup", None)
        return render_template(
            "signup.html",
            step="contact",
            error="Too many incorrect codes. Please start again."
        )

    if len(code) != 6 or not auth_store.otp_matches(pending.get("otp_hash"), code):
        return render_template(
            "signup.html",
            step="otp",
            contact=pending.get("email"),
            otp_preview=pending.get("otp_preview"),
            error="Invalid verification code. Please try again."
        )

    pending["verified"] = True
    session["signup"] = pending

    return render_template(
        "signup.html",
        step="account",
        contact=pending.get("email")
    )


@app.route("/signup/resend", methods=["POST"])
def signup_resend():

    pending = signup_pending()

    if not pending:
        return render_template(
            "signup.html",
            step="contact",
            error="Your verification session expired. Please start again."
        )

    preview, error = start_signup_otp(pending.get("email"))

    if error:
        return render_template(
            "signup.html",
            step="otp",
            contact=pending.get("email"),
            error=error
        )

    refreshed = session.get("signup") or {}

    return render_template(
        "signup.html",
        step="otp",
        contact=refreshed.get("email"),
        otp_preview=preview,
        info="A new verification code has been sent."
    )


@app.route("/signup/complete", methods=["POST"])
def signup_complete():

    pending = signup_pending()

    if not pending or not pending.get("verified"):
        return render_template(
            "signup.html",
            step="contact",
            error="Please verify your email before creating an account."
        )

    username, username_error = auth_store.validate_username(
        request.form.get("username")
    )
    password_error = auth_store.validate_password(
        request.form.get("password"),
        request.form.get("confirm_password")
    )

    if username_error or password_error:
        return render_template(
            "signup.html",
            step="account",
            contact=pending.get("email"),
            username=request.form.get("username", ""),
            error=username_error or password_error
        )

    if username in USERS:
        return render_template(
            "signup.html",
            step="account",
            contact=pending.get("email"),
            username=username,
            error="This username is reserved. Please choose another."
        )

    store = auth_store.load_users()

    if auth_store.find_user(store, username=username):
        return render_template(
            "signup.html",
            step="account",
            contact=pending.get("email"),
            username=username,
            error="This username is already taken."
        )

    auth_store.create_user(
        username=username,
        password=request.form.get("password"),
        email=pending.get("email"),
    )

    session.pop("signup", None)

    return redirect(
        url_for("login", registered="1")
    )


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
                **empty_dashboard_context(error="No file uploaded")
            )

        file = request.files["file"]

        if file.filename == "":

            return render_template(
                "index.html",
                **empty_dashboard_context(error="No file selected")
            )

        if not file.filename.lower().endswith(".xlsx"):

            return render_template(
                "index.html",
                **empty_dashboard_context(
                    error="Please upload an Excel (.xlsx) file"
                )
            )

        pending_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            "pending_upload.xlsx"
        )

        try:

            file.save(pending_path)

            test_df = pd.read_excel(pending_path)

            if test_df.empty:

                return render_template(
                    "index.html",
                    **empty_dashboard_context(
                        error="The Excel file has no rows to analyze."
                    )
                )

            session["pending_upload"] = pending_path
            session["pending_filename"] = file.filename

            return redirect(
                url_for("map_columns")
            )

        except Exception as e:

            return render_template(
                "index.html",
                **empty_dashboard_context(
                    error=f"Error processing Excel file: {str(e)}"
                )
            )

    return render_template(
        "index.html",
        **empty_dashboard_context()
    )


# ============================================================
# LOAD DATA
# ============================================================

def clean_results_frame(df):

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

    df = df.copy()

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

    df["Name"] = df["Name"].map(normalize_text)

    df["USN"] = df["USN"].map(normalize_text)

    df["Subject Name"] = df["Subject Name"].map(normalize_text)

    df["Subject Code"] = df["Subject Code"].map(normalize_text)

    df = df[
        (df["USN"] != "")
        & (df["Name"] != "")
        & (df["Subject Name"] != "")
    ]

    if df.empty:
        return df

    df = (
        df.groupby(
            ["USN", "Subject Name", "Subject Code"],
            as_index=False,
            sort=False
        )
        .agg({
            "Name": "first",
            "Marks": "max"
        })
    )

    return df


def finalize_uploaded_dataset(df, original_name):

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        "uploaded_data.xlsx"
    )

    cleaned = clean_results_frame(df)

    if cleaned is None or cleaned.empty:
        raise ValueError("No valid student rows after cleaning the mapped columns.")

    cleaned.to_excel(filepath, index=False)
    session["uploaded_file"] = filepath
    session.pop("pending_upload", None)
    session.pop("pending_filename", None)

    student_df = create_student_analysis(cleaned)
    stats = insights.batch_stats(
        student_df,
        cleaned["Subject Name"].nunique()
    )
    insights.archive_batch(filepath, original_name, stats)
    return filepath


def load_data():

    filepath = session.get("uploaded_file")

    if (
        not filepath
        or not os.path.exists(filepath)
    ):
        return None

    df = pd.read_excel(filepath)
    return clean_results_frame(df)


def load_batch_frame(batch_id):

    if batch_id == "current":
        return load_data()

    batch = insights.get_batch(batch_id)

    if not batch or not os.path.isfile(batch.get("path", "")):
        return None

    return clean_results_frame(pd.read_excel(batch["path"]))


# ============================================================
# STUDENT ANALYSIS
# ============================================================

def create_student_analysis(df):

    records = []

    if df is None or df.empty:

        return pd.DataFrame(
            columns=[
                "USN",
                "Name",
                "Subjects",
                "Total",
                "Average",
                "Percentage",
                "Passed Subjects",
                "Failed Subjects",
                "Result",
                "Rank"
            ]
        )

    grouped = df.groupby("USN", sort=False)

    for usn, group in grouped:

        name = group["Name"].iloc[0]

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

            "Passed Subjects": passed_subjects,

            "Failed Subjects": failed_subjects,

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

    columns = [
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

    if df is None or df.empty:

        return pd.DataFrame(
            columns=columns
        )

    records = []

    for subject, group in df.groupby(
        "Subject Name"
    ):

        average = group["Marks"].mean()

        highest = group["Marks"].max()

        lowest = group["Marks"].min()

        total_students = len(group)

        pass_students = int(
            (
                group["Marks"] >= PASS_MARK
            ).sum()
        )

        fail_students = int(
            (
                group["Marks"] < PASS_MARK
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


def get_selected_filters():

    selected_student = request.args.get("student", "All") or "All"
    selected_subject = request.args.get("subject", "All") or "All"
    selected_result = request.args.get("result", "All") or "All"

    return selected_student, selected_subject, selected_result


def apply_dashboard_filters(
    df,
    student_df,
    selected_student,
    selected_subject,
    selected_result
):

    filtered_df = df.copy()

    if selected_student != "All":

        filtered_df = filtered_df[
            filtered_df["USN"] == selected_student
        ]

    if selected_subject != "All":

        filtered_df = filtered_df[
            filtered_df["Subject Name"] == selected_subject
        ]

    if selected_result != "All":

        result_students = (
            student_df[
                student_df["Result"] == selected_result
            ]["USN"]
            .tolist()
        )

        filtered_df = filtered_df[
            filtered_df["USN"].isin(result_students)
        ]

    return filtered_df


def create_at_risk_students(student_df):

    columns = [
        "Rank",
        "Name",
        "USN",
        "Failed Subjects",
        "Passed Subjects",
        "Percentage",
        "Result"
    ]

    if student_df is None or student_df.empty:

        return pd.DataFrame(columns=columns)

    at_risk_df = student_df[
        student_df["Failed Subjects"] >= 1
    ].copy()

    if at_risk_df.empty:

        return pd.DataFrame(columns=columns)

    return (
        at_risk_df
        .sort_values(
            by=["Failed Subjects", "Percentage"],
            ascending=[False, True]
        )
        .reset_index(drop=True)
    )


def filters_are_active(
    selected_student,
    selected_subject,
    selected_result
):

    return any(
        value != "All"
        for value in (
            selected_student,
            selected_subject,
            selected_result
        )
    )


def filter_summary_label(
    selected_student,
    selected_subject,
    selected_result
):

    return (
        f"Student: {selected_student} | "
        f"Subject: {selected_subject} | "
        f"Result: {selected_result}"
    )


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

        # ====================================================
        # COMPLETE ANALYSIS
        # ====================================================

        student_df = create_student_analysis(df)

        subject_df = create_subject_analysis(df)

        # ====================================================
        # FILTER VALUES
        # ====================================================

        (
            selected_student,
            selected_subject,
            selected_result
        ) = get_selected_filters()

        filtered_df = apply_dashboard_filters(
            df,
            student_df,
            selected_student,
            selected_subject,
            selected_result
        )

        # ====================================================
        # FILTERED ANALYSIS
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

        at_risk_df = create_at_risk_students(
            filtered_student_df
        )

        at_risk_count = len(at_risk_df)

        # ====================================================
        # KPI CALCULATIONS
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

        # ====================================================
        # TOPPER
        # ====================================================

        topper_name = "N/A"

        topper_marks = 0

        if not filtered_student_df.empty:

            topper = filtered_student_df.iloc[0]

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

        for value in filtered_student_df["Percentage"]:

            category = performance_category(
                value
            )

            distribution[category] += 1

        # ====================================================
        # 1. AVERAGE MARKS BY SUBJECT - DONUT
        # ====================================================

        subject_colors = [
            "#6366f1",
            "#06b6d4",
            "#84cc16",
            "#f59e0b",
            "#f97316",
            "#ec4899",
            "#8b5cf6",
            "#14b8a6"
        ]

        subject_fig = go.Figure(
            go.Pie(

                labels=(
                    filtered_subject_df["Subject"]
                    .tolist()
                ),

                values=(
                    filtered_subject_df["Average"]
                    .tolist()
                ),

                hole=0.58,

                textinfo="percent",

                textfont={
                    "color": "#ffffff",
                    "size": 11
                },

                marker={
                    "colors": subject_colors[
                        :len(filtered_subject_df)
                    ],
                    "line": {
                        "color": "#0b1428",
                        "width": 2
                    }
                },

                hovertemplate=(
                    "%{label}"
                    "<br>Average: %{value:.2f}"
                    "<extra></extra>"
                )
            )
        )

        subject_layout = get_chart_layout(

            title={
                "text": "Average Marks by Subject",
                "font": {
                    "color": "#ffffff",
                    "size": 14
                }
            },

            showlegend=True,

            legend={
                "font": {
                    "color": "#e2e8f0",
                    "size": 13
                },
                "bgcolor": "rgba(0,0,0,0)",
                "x": 1.02,
                "y": 0.5
            },

            margin={
                "l": 20,
                "r": 130,
                "t": 48,
                "b": 20
            },

            height=300,

            annotations=[

                {
                    "text": f"{average_marks:.1f}",
                    "showarrow": False,
                    "font": {
                        "color": "#ffffff",
                        "size": 20
                    }
                },

                {
                    "text": "Class Avg",
                    "showarrow": False,
                    "y": 0.39,
                    "font": {
                        "color": "#94a3b8",
                        "size": 9
                    }
                }
            ]
        )

        subject_fig.update_layout(
            **subject_layout
        )

        subject_chart = pyo.plot(
            subject_fig,
            output_type="div",
            include_plotlyjs=False
        )

        # ====================================================
        # 2. SUBJECT DIFFICULTY - GAUGE
        # ====================================================

        overall_difficulty = (

            float(
                filtered_subject_df[
                    "Difficulty Score"
                ].mean()
            )

            if not filtered_subject_df.empty

            else 0
        )

        difficulty_level = (

            "High"

            if overall_difficulty >= 50

            else (

                "Medium"

                if overall_difficulty >= 30

                else "Low"
            )
        )

        difficulty_fig = go.Figure(

            go.Indicator(

                mode="gauge+number",

                value=round(
                    overall_difficulty,
                    1
                ),

                number={
                    "font": {
                        "color": "#ffffff",
                        "size": 28
                    }
                },

                gauge={

                    "axis": {
                        "range": [0, 100],
                        "tickcolor": "#cbd5e1",
                        "tickfont": {
                            "color": "#cbd5e1",
                            "size": 9
                        }
                    },

                    "bar": {
                        "color": "#f8fafc",
                        "thickness": 0.16
                    },

                    "bgcolor": "#0b1428",

                    "borderwidth": 0,

                    "steps": [

                        {
                            "range": [0, 30],
                            "color": "#22c55e"
                        },

                        {
                            "range": [30, 50],
                            "color": "#facc15"
                        },

                        {
                            "range": [50, 75],
                            "color": "#f97316"
                        },

                        {
                            "range": [75, 100],
                            "color": "#ef4444"
                        }
                    ],

                    "threshold": {
                        "line": {
                            "color": "#ffffff",
                            "width": 3
                        },
                        "thickness": 0.75,
                        "value": overall_difficulty
                    }
                },

                domain={
                    "x": [0, 1],
                    "y": [0, 1]
                }
            )
        )

        difficulty_layout = get_chart_layout(

            title={
                "text": "Subject Difficulty Index",
                "font": {
                    "color": "#ffffff",
                    "size": 14
                }
            },

            height=300,

            margin={
                "l": 20,
                "r": 20,
                "t": 48,
                "b": 35
            },

            annotations=[

                {
                    "text": (
                        f"Overall Difficulty "
                        f"({difficulty_level})"
                    ),
                    "showarrow": False,
                    "y": 0.08,
                    "font": {
                        "color": "#facc15",
                        "size": 10
                    }
                }
            ]
        )

        difficulty_fig.update_layout(
            **difficulty_layout
        )

        difficulty_chart = pyo.plot(
            difficulty_fig,
            output_type="div",
            include_plotlyjs=False
        )

        # ====================================================
        # 3. MARKS DISTRIBUTION - AREA CHART
        # ====================================================

        bins = [
            0,
            20,
            40,
            60,
            80,
            100
        ]

        labels = [
            "0-20",
            "20-40",
            "40-60",
            "60-80",
            "80-100"
        ]

        counts = []

        for i in range(
            len(bins) - 1
        ):

            left = bins[i]

            right = bins[i + 1]

            if i == len(bins) - 2:

                count = int(
                    (
                        (filtered_df["Marks"] >= left)
                        &
                        (filtered_df["Marks"] <= right)
                    ).sum()
                )

            else:

                count = int(
                    (
                        (filtered_df["Marks"] >= left)
                        &
                        (filtered_df["Marks"] < right)
                    ).sum()
                )

            counts.append(count)

        histogram_fig = go.Figure(

            go.Scatter(

                x=labels,

                y=counts,

                mode="lines+markers+text",

                text=counts,

                textposition="top center",

                textfont={
                    "color": "#ffffff",
                    "size": 10
                },

                line={
                    "color": "#22d3ee",
                    "width": 3,
                    "shape": "spline"
                },

                marker={
                    "color": "#22d3ee",
                    "size": 8,
                    "line": {
                        "color": "#ffffff",
                        "width": 1
                    }
                },

                fill="tozeroy",

                fillcolor=(
                    "rgba(34,211,238,0.12)"
                ),

                hovertemplate=(
                    "Marks: %{x}"
                    "<br>Students: %{y}"
                    "<extra></extra>"
                )
            )
        )

        histogram_layout = get_chart_layout(

            title={
                "text": "Marks Distribution",
                "font": {
                    "color": "#ffffff",
                    "size": 14
                }
            },

            xaxis_title="Marks Range",

            yaxis_title="Students",

            height=300
        )

        histogram_fig.update_layout(
            **histogram_layout
        )

        histogram_chart = pyo.plot(
            histogram_fig,
            output_type="div",
            include_plotlyjs=False
        )

        # ====================================================
        # 4. PASS VS FAIL - DONUT
        # ====================================================

        pie_fig = go.Figure(

            go.Pie(

                labels=[
                    "Passed",
                    "Failed"
                ],

                values=[
                    pass_students,
                    fail_students
                ],

                hole=0.62,

                textinfo="percent",

                textfont={
                    "color": "#ffffff",
                    "size": 11
                },

                marker={
                    "colors": [
                        "#22c55e",
                        "#ef4444"
                    ],
                    "line": {
                        "color": "#0b1428",
                        "width": 3
                    }
                },

                hovertemplate=(
                    "%{label}: %{value}"
                    "<br>%{percent}"
                    "<extra></extra>"
                )
            )
        )

        pie_layout = get_chart_layout(

            title={
                "text": "Overall Pass vs Fail",
                "font": {
                    "color": "#ffffff",
                    "size": 14
                }
            },

            height=300,

            margin={
                "l": 20,
                "r": 110,
                "t": 48,
                "b": 20
            },

            legend={
                "font": {
                    "color": "#e2e8f0",
                    "size": 13
                },
                "bgcolor": "rgba(0,0,0,0)",
                "x": 1.0,
                "y": 0.5
            },

            annotations=[

                {
                    "text": f"{pass_percentage:.1f}%",
                    "showarrow": False,
                    "font": {
                        "color": "#ffffff",
                        "size": 21
                    }
                },

                {
                    "text": "Pass Rate",
                    "showarrow": False,
                    "y": 0.40,
                    "font": {
                        "color": "#94a3b8",
                        "size": 9
                    }
                }
            ]
        )

        pie_fig.update_layout(
            **pie_layout
        )

        pie_chart = pyo.plot(
            pie_fig,
            output_type="div",
            include_plotlyjs=False
        )

        # ====================================================
        # 5. TOP 5 STUDENTS - LEADERBOARD
        # ====================================================

        top5 = (
            filtered_student_df
            .head(5)
            .sort_values(
                "Percentage",
                ascending=True
            )
        )

        rank_colors = [
            "#22c55e",
            "#14b8a6",
            "#06b6d4",
            "#6366f1",
            "#a855f7"
        ]

        ranking_fig = go.Figure(

            go.Bar(

                x=top5[
                    "Percentage"
                ].tolist(),

                y=top5[
                    "Name"
                ].tolist(),

                orientation="h",

                text=[
                    f"{x:.2f}%"
                    for x in top5[
                        "Percentage"
                    ]
                ],

                textposition="outside",

                textfont={
                    "color": "#ffffff",
                    "size": 10
                },

                marker={
                    "color": rank_colors[
                        :len(top5)
                    ],
                    "line": {
                        "color": (
                            "rgba(255,255,255,0.12)"
                        ),
                        "width": 1
                    }
                },

                hovertemplate=(
                    "%{y}"
                    "<br>Percentage: %{x:.2f}%"
                    "<extra></extra>"
                )
            )
        )

        ranking_layout = get_chart_layout(

            title={
                "text": "Top 5 Students",
                "font": {
                    "color": "#ffffff",
                    "size": 14
                }
            },

            xaxis_title="Percentage",

            xaxis={
                **CHART_BASE["xaxis"],
                "range": [0, 105]
            },

            yaxis={
                **CHART_BASE["yaxis"],
                "automargin": True
            },

            height=300,

            margin={
                "l": 100,
                "r": 48,
                "t": 48,
                "b": 40
            },

            showlegend=False
        )

        ranking_fig.update_layout(
            **ranking_layout
        )

        ranking_chart = pyo.plot(
            ranking_fig,
            output_type="div",
            include_plotlyjs=False
        )

        # ====================================================
        # 6. PERFORMANCE CATEGORIES - BAR
        # ====================================================

        performance_fig = go.Figure(

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

                textposition="outside",

                textfont={
                    "color": "#ffffff",
                    "size": 14
                },

                marker={
                    "color": [
                        "#6366f1",
                        "#0ea5e9",
                        "#facc15",
                        "#f97316",
                        "#ef4444"
                    ],
                    "line": {
                        "color": "rgba(255,255,255,0.12)",
                        "width": 1
                    }
                },

                hovertemplate=(
                    "%{x}: %{y} students"
                    "<extra></extra>"
                )
            )
        )

        performance_layout = get_chart_layout(

            title={
                "text": "Student Performance",
                "font": {
                    "color": "#ffffff",
                    "size": 16
                }
            },

            xaxis_title="Category",

            yaxis_title="Students",

            height=300,

            margin={
                "l": 52,
                "r": 20,
                "t": 52,
                "b": 56
            },

            showlegend=False,

            xaxis={
                **CHART_BASE["xaxis"],
                "tickfont": {
                    "color": "#e2e8f0",
                    "size": 13
                },
                "title_font": {
                    "color": "#e2e8f0",
                    "size": 12
                }
            },

            yaxis={
                **CHART_BASE["yaxis"],
                "rangemode": "tozero",
                "tickfont": {
                    "color": "#cbd5e1",
                    "size": 12
                },
                "title_font": {
                    "color": "#e2e8f0",
                    "size": 12
                }
            }
        )

        performance_fig.update_layout(
            **performance_layout
        )

        performance_chart = pyo.plot(
            performance_fig,
            output_type="div",
            include_plotlyjs=False
        )

        # ====================================================
        # 7. SUBJECT PERFORMANCE HEATMAP
        # ====================================================

        heatmap_students = (
            filtered_student_df
            .head(5)
        )

        subject_names = (
            filtered_subject_df[
                "Subject"
            ]
            .tolist()
        )

        heat_z = []

        heat_y = []

        for _, row in heatmap_students.iterrows():

            usn = row["USN"]

            marks = []

            for subject in subject_names:

                vals = filtered_df[
                    (filtered_df["USN"] == usn)
                    &
                    (
                        filtered_df[
                            "Subject Name"
                        ] == subject
                    )
                ]["Marks"]

                if not vals.empty:

                    marks.append(
                        float(
                            vals.iloc[0]
                        )
                    )

                else:

                    marks.append(0)

            heat_z.append(marks)

            heat_y.append(
                row["Name"]
            )

        if not heat_z:

            heat_z = [[0]]

        if not heat_y:

            heat_y = ["No Student"]

        if not subject_names:

            subject_names = ["No Subject"]

        heatmap_fig = go.Figure(

            go.Heatmap(

                z=heat_z,

                x=subject_names,

                y=heat_y,

                colorscale=[

                    [
                        0,
                        "#ef4444"
                    ],

                    [
                        0.35,
                        "#f59e0b"
                    ],

                    [
                        0.60,
                        "#facc15"
                    ],

                    [
                        0.80,
                        "#22c55e"
                    ],

                    [
                        1,
                        "#06b6d4"
                    ]
                ],

                zmin=0,

                zmax=100,

                text=[
                    [
                        f"{v:.0f}"
                        for v in row
                    ]
                    for row in heat_z
                ],

                texttemplate="%{text}",

                textfont={
                    "color": "#ffffff",
                    "size": 9
                },

                hovertemplate=(
                    "%{y}"
                    "<br>%{x}: %{z:.1f}"
                    "<extra></extra>"
                ),

                colorbar={
                    "title": {
                        "text": "Marks",
                        "font": {
                            "color": "#e2e8f0",
                            "size": 9
                        }
                    },

                    "tickfont": {
                        "color": "#cbd5e1",
                        "size": 8
                    }
                }
            )
        )

        heatmap_layout = get_chart_layout(

            title={
                "text": "Subject Performance Heatmap",
                "font": {
                    "color": "#ffffff",
                    "size": 14
                }
            },

            height=300,

            margin={
                "l": 80,
                "r": 30,
                "t": 48,
                "b": 55
            },

            xaxis={
                **CHART_BASE["xaxis"],
                "tickangle": -25
            }
        )

        heatmap_fig.update_layout(
            **heatmap_layout
        )

        heatmap_chart = pyo.plot(
            heatmap_fig,
            output_type="div",
            include_plotlyjs=False
        )

        # ====================================================
        # 8. SUBJECT AVERAGE TREND
        # ====================================================

        trend_subjects = (
            filtered_subject_df
            .sort_values("Average")
        )

        trend_x = (
            trend_subjects[
                "Subject"
            ]
            .tolist()
        )

        trend_y = (
            trend_subjects[
                "Average"
            ]
            .tolist()
        )

        trend_fig = go.Figure(

            go.Scatter(

                x=trend_x,

                y=trend_y,

                mode="lines+markers+text",

                text=[
                    f"{v:.1f}%"
                    for v in trend_y
                ],

                textposition="top center",

                textfont={
                    "color": "#ffffff",
                    "size": 9
                },

                line={
                    "color": "#22d3ee",
                    "width": 3,
                    "shape": "spline"
                },

                marker={
                    "color": "#22d3ee",
                    "size": 8,
                    "line": {
                        "color": "#ffffff",
                        "width": 1
                    }
                },

                fill="tozeroy",

                fillcolor=(
                    "rgba(34,211,238,0.10)"
                ),

                hovertemplate=(
                    "%{x}"
                    "<br>Average: %{y:.2f}"
                    "<extra></extra>"
                )
            )
        )

        trend_layout = get_chart_layout(

            title={
                "text": "Subject Average Trend",
                "font": {
                    "color": "#ffffff",
                    "size": 14
                }
            },

            xaxis_title="Subject",

            yaxis_title="Average (%)",

            height=300,

            xaxis={
                **CHART_BASE["xaxis"],
                "tickangle": -25
            }
        )

        trend_fig.update_layout(
            **trend_layout
        )

        trend_chart = pyo.plot(
            trend_fig,
            output_type="div",
            include_plotlyjs=False
        )

        # ====================================================
        # 9. TOP 5 STUDENTS - RADAR
        # ====================================================

        radar_fig = go.Figure()

        radar_colors = [
            "#7c3aed",
            "#ec4899",
            "#f59e0b",
            "#06b6d4",
            "#22c55e"
        ]

        for idx, (_, row) in enumerate(
            heatmap_students.iterrows()
        ):

            values = []

            for subject in subject_names:

                vals = filtered_df[
                    (
                        filtered_df["USN"]
                        == row["USN"]
                    )
                    &
                    (
                        filtered_df[
                            "Subject Name"
                        ]
                        == subject
                    )
                ]["Marks"]

                if not vals.empty:

                    values.append(
                        float(
                            vals.iloc[0]
                        )
                    )

                else:

                    values.append(0)

            if values:

                radar_r = (
                    values
                    + [values[0]]
                )

                radar_theta = (
                    subject_names
                    + [subject_names[0]]
                )

            else:

                radar_r = [0]

                radar_theta = [
                    "No Subject"
                ]

            radar_fig.add_trace(

                go.Scatterpolar(

                    r=radar_r,

                    theta=radar_theta,

                    mode="lines",

                    fill="toself",

                    name=str(
                        row["Name"]
                    ),

                    line={
                        "color": radar_colors[
                            idx
                            % len(radar_colors)
                        ],
                        "width": 2
                    },

                    fillcolor=(
                        "rgba(99,102,241,0.04)"
                    ),

                    hovertemplate=(
                        "%{theta}: %{r:.1f}"
                        "<extra></extra>"
                    )
                )
            )

        radar_layout = get_chart_layout(

            title={
                "text": "Top 5 Students Comparison",
                "font": {
                    "color": "#ffffff",
                    "size": 14
                }
            },

            height=300,

            margin={
                "l": 55,
                "r": 75,
                "t": 48,
                "b": 35
            },

            polar={

                "bgcolor": "rgba(0,0,0,0)",

                "radialaxis": {
                    "range": [0, 100],
                    "color": "#94a3b8",
                    "gridcolor": (
                        "rgba(148,163,184,0.15)"
                    ),
                    "tickfont": {
                        "color": "#94a3b8",
                        "size": 8
                    }
                },

                "angularaxis": {
                    "color": "#cbd5e1",
                    "gridcolor": (
                        "rgba(148,163,184,0.15)"
                    ),
                    "tickfont": {
                        "color": "#cbd5e1",
                        "size": 9
                    }
                }
            },

            legend={
                "font": {
                    "color": "#e2e8f0",
                    "size": 12
                },
                "bgcolor": "rgba(0,0,0,0)",
                "x": 1.0,
                "y": 0.5
            }
        )

        radar_fig.update_layout(
            **radar_layout
        )

        radar_chart = pyo.plot(
            radar_fig,
            output_type="div",
            include_plotlyjs=False
        )

        # ====================================================
        # DROPDOWN DATA
        # ====================================================

        students = (
            student_df[["USN", "Name"]]
            .drop_duplicates()
            .sort_values("Name")
            .to_dict(orient="records")
        )

        subjects = sorted(
            df["Subject Name"]
            .dropna()
            .unique()
            .tolist()
        )

        # ====================================================
        # RENDER DASHBOARD
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

            at_risk_count=(
                at_risk_count
            ),

            at_risk_students=(
                at_risk_df.to_dict(
                    orient="records"
                )
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
            ),

            heatmap_chart=(
                heatmap_chart
            ),

            trend_chart=(
                trend_chart
            ),

            radar_chart=(
                radar_chart
            )
        )

    except Exception as e:

        print(
            "Dashboard Error:",
            str(e)
        )

        return render_template(

            "index.html",

            **empty_dashboard_context(

                error=(
                    f"Error processing Excel file: {str(e)}"
                )
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

        if df is None:

            return redirect(
                url_for("index")
            )

        student_df = (
            create_student_analysis(df)
        )

        usn = normalize_text(usn)

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

        if marks_df.empty:

            return redirect(
                url_for("dashboard")
            )

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

        peer_percentages = student_df[
            student_df["USN"] != usn
        ]["Percentage"].tolist()

        return render_template(

            "student_profile.html",

            student=student.to_dict(),

            marks=marks_df.to_dict(
                orient="records"
            ),

            strongest=strongest.to_dict(),

            weakest=weakest.to_dict(),

            pass_mark=PASS_MARK,

            peer_percentages=peer_percentages,

            selected_student="All",
            selected_subject="All",
            selected_result="All",
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

        (
            selected_student,
            selected_subject,
            selected_result
        ) = get_selected_filters()

        overall_student_df = (
            create_student_analysis(df)
        )

        df = apply_dashboard_filters(
            df,
            overall_student_df,
            selected_student,
            selected_subject,
            selected_result
        )

        student_df = (
            create_student_analysis(df)
        )

        subject_df = (
            create_subject_analysis(df)
        )

        at_risk_df = create_at_risk_students(
            student_df
        )

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

                "At-Risk Students",

                "Topper",

                "Filter - Student",

                "Filter - Subject",

                "Filter - Result"
            ],

            "Value": [

                len(student_df),

                df[
                    "Subject Name"
                ].nunique() if not df.empty else 0,

                round(
                    df["Marks"].mean(),
                    2
                ) if not df.empty else 0,

                pass_students,

                fail_students,

                pass_percentage,

                len(at_risk_df),

                (
                    student_df.iloc[0]["Name"]

                    if not student_df.empty

                    else "N/A"
                ),

                selected_student,

                selected_subject,

                selected_result
            ]
        })

        # ====================================================
        # CREATE EXCEL
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

            at_risk_df.to_excel(
                writer,
                index=False,
                sheet_name="At Risk Students"
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
                ),

                (
                    "At Risk Students",
                    at_risk_df
                )
            ]:

                worksheet = writer.sheets[
                    sheet_name
                ]

                worksheet.freeze_panes(
                    1,
                    0
                )

                # ------------------------------------------------
                # HEADER FORMAT
                # ------------------------------------------------

                for col_num, column in enumerate(
                    dataframe.columns
                ):

                    worksheet.write(
                        0,
                        col_num,
                        column,
                        header_format
                    )

                # ------------------------------------------------
                # COLUMN WIDTH
                # ------------------------------------------------

                for col_num, column in enumerate(
                    dataframe.columns
                ):

                    if dataframe.empty:

                        width = len(
                            str(column)
                        ) + 3

                    else:

                        max_length = (
                            dataframe[
                                column
                            ]
                            .astype(str)
                            .map(len)
                            .max()
                        )

                        width = max(
                            len(
                                str(column)
                            ) + 3,
                            min(
                                30,
                                max_length + 3
                            )
                        )

                    worksheet.set_column(
                        col_num,
                        col_num,
                        width
                    )

                # ------------------------------------------------
                # AUTOFILTER
                # ------------------------------------------------

                if not dataframe.empty:

                    worksheet.autofilter(
                        0,
                        0,
                        len(dataframe),
                        len(
                            dataframe.columns
                        ) - 1
                    )

        output.seek(0)

        return send_file(

            output,

            download_name=(
                "Student_Result_Analysis_Filtered.xlsx"
                if filters_are_active(
                    selected_student,
                    selected_subject,
                    selected_result
                )
                else "Student_Result_Analysis_Report.xlsx"
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

        if df is None:

            return redirect(
                url_for("index")
            )

        (
            selected_student,
            selected_subject,
            selected_result
        ) = get_selected_filters()

        overall_student_df = (
            create_student_analysis(df)
        )

        df = apply_dashboard_filters(
            df,
            overall_student_df,
            selected_student,
            selected_subject,
            selected_result
        )

        student_df = (
            create_student_analysis(df)
        )

        subject_df = (
            create_subject_analysis(df)
        )

        at_risk_df = create_at_risk_students(
            student_df
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

        # ====================================================
        # TITLE
        # ====================================================

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

            Paragraph(

                "Applied filters — "
                + filter_summary_label(
                    selected_student,
                    selected_subject,
                    selected_result
                ),

                styles["Normal"]
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
            df["Subject Name"].nunique()
            if not df.empty
            else 0
        )

        average = (
            round(
                df["Marks"].mean(),
                2
            )
            if not df.empty
            else 0
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

            [
                "Metric",
                "Value"
            ],

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
                "At-Risk Students",
                len(at_risk_df)
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
        # AT-RISK STUDENTS
        # ====================================================

        elements.append(

            Paragraph(
                "At-Risk Students",
                heading_style
            )
        )

        at_risk_data = [

            [
                "Name",
                "USN",
                "Failed Subjects",
                "Passed Subjects",
                "Percentage",
                "Result"
            ]
        ]

        if at_risk_df.empty:

            at_risk_data.append([
                "No at-risk students in this view",
                "-",
                "-",
                "-",
                "-",
                "-"
            ])

        else:

            for _, row in (
                at_risk_df.head(20).iterrows()
            ):

                at_risk_data.append([

                    row["Name"],

                    row["USN"],

                    row["Failed Subjects"],

                    row["Passed Subjects"],

                    f'{row["Percentage"]}%',

                    row["Result"]
                ])

        at_risk_table = Table(
            at_risk_data,
            repeatRows=1
        )

        at_risk_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#7F1D1D"
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
            at_risk_table
        )

        # ====================================================
        # STUDENT RANKINGS
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
            student_df
            .head(20)
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

        doc.build(
            elements
        )

        output.seek(0)

        return send_file(

            output,

            download_name=(
                "Student_Result_Analysis_Filtered.pdf"
                if filters_are_active(
                    selected_student,
                    selected_subject,
                    selected_result
                )
                else "Student_Result_Analysis_Report.pdf"
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
# COLUMN MAPPING WIZARD
# ============================================================

@app.route("/map-columns", methods=["GET", "POST"])
def map_columns():

    if "user" not in session:
        return redirect(url_for("login"))

    pending_path = session.get("pending_upload")

    if not pending_path or not os.path.isfile(pending_path):
        return redirect(url_for("index"))

    try:
        raw_df = pd.read_excel(pending_path)
    except Exception as exc:
        return render_template(
            "index.html",
            **empty_dashboard_context(
                error=f"Could not read the Excel file: {exc}"
            )
        )

    columns = [str(column) for column in raw_df.columns.tolist()]
    guessed, unused = insights.guess_column_mapping(columns)
    recipe = insights.matching_recipe(columns)

    if recipe and recipe.get("mapping"):
        guessed = recipe["mapping"]

    if request.method == "POST":
        mapping = {
            field: (request.form.get(field) or "").strip()
            for field in insights.REQUIRED_FIELDS
        }

        if len(set(mapping.values())) < len(mapping.values()) or any(
            not value for value in mapping.values()
        ):
            return render_template(
                "map_columns.html",
                columns=columns,
                mapping=mapping,
                unused=unused,
                recipes=insights.load_recipes(),
                preview=raw_df.head(6).to_dict(orient="records"),
                filename=session.get("pending_filename", "upload.xlsx"),
                error="Map every required field to a different Excel column.",
                selected_student="All",
                selected_subject="All",
                selected_result="All",
            )

        try:
            mapped = insights.apply_column_mapping(raw_df, mapping)
            recipe_name = (request.form.get("recipe_name") or "").strip()
            if recipe_name:
                insights.save_recipe(recipe_name, columns, mapping)
            finalize_uploaded_dataset(
                mapped,
                session.get("pending_filename", "upload.xlsx"),
            )
            return redirect(url_for("dashboard"))
        except Exception as exc:
            return render_template(
                "map_columns.html",
                columns=columns,
                mapping=mapping,
                unused=unused,
                recipes=insights.load_recipes(),
                preview=raw_df.head(6).to_dict(orient="records"),
                filename=session.get("pending_filename", "upload.xlsx"),
                error=str(exc),
                selected_student="All",
                selected_subject="All",
                selected_result="All",
            )

    return render_template(
        "map_columns.html",
        columns=columns,
        mapping=guessed,
        unused=unused,
        recipes=insights.load_recipes(),
        preview=raw_df.head(6).to_dict(orient="records"),
        filename=session.get("pending_filename", "upload.xlsx"),
        matched_recipe=(recipe or {}).get("name"),
        selected_student="All",
        selected_subject="All",
        selected_result="All",
    )


# ============================================================
# INSIGHTS HUB
# ============================================================

@app.route("/insights")
def insights_hub():

    if "user" not in session:
        return redirect(url_for("login"))

    if "uploaded_file" not in session:
        return redirect(url_for("index"))

    df = load_data()

    if df is None:
        return redirect(url_for("index"))

    student_df = create_student_analysis(df)
    queue = insights.counseling_queue(df, student_df, PASS_MARK)
    pairs, chain_subjects, chain_chart = insights.failure_chains(df, PASS_MARK)
    flags = insights.anomaly_flags(df, PASS_MARK)
    backlog_df, backlog_summary = insights.backlog_planner(df, PASS_MARK)
    batches = insights.list_batches()

    left_id = request.args.get("left") or (
        batches[1]["id"] if len(batches) > 1 else "current"
    )
    right_id = request.args.get("right") or "current"

    left_df = load_batch_frame(left_id)
    right_df = load_batch_frame(right_id)
    left_students = create_student_analysis(left_df) if left_df is not None else create_student_analysis(df)
    right_students = create_student_analysis(right_df) if right_df is not None else student_df
    left_stats = insights.batch_stats(
        left_students,
        0 if left_df is None else left_df["Subject Name"].nunique(),
    )
    right_stats = insights.batch_stats(
        right_students,
        0 if right_df is None else right_df["Subject Name"].nunique(),
    )
    comparison = insights.compare_student_sets(left_students, right_students)

    return render_template(
        "insights.html",
        counseling=queue,
        chains=pairs,
        chain_chart=chain_chart,
        anomalies=flags,
        backlogs=backlog_df.head(80).to_dict(orient="records"),
        backlog_summary=backlog_summary.to_dict(orient="records"),
        backlog_total=len(backlog_df),
        batches=batches,
        left_id=left_id,
        right_id=right_id,
        left_stats=left_stats,
        right_stats=right_stats,
        comparison=comparison,
        pass_mark=PASS_MARK,
        selected_student="All",
        selected_subject="All",
        selected_result="All",
    )


@app.route("/download-backlog")
def download_backlog():

    if "user" not in session:
        return redirect(url_for("login"))

    df = load_data()

    if df is None:
        return redirect(url_for("index"))

    backlog_df, summary_df = insights.backlog_planner(df, PASS_MARK)
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        backlog_df.to_excel(writer, sheet_name="Backlogs", index=False)
        summary_df.to_excel(writer, sheet_name="By Subject", index=False)

    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="supplementary_backlog_planner.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/student/<usn>/share", methods=["POST"])
def share_student_card(usn):

    if "user" not in session:
        return redirect(url_for("login"))

    df = load_data()

    if df is None:
        return redirect(url_for("index"))

    usn = normalize_text(usn)
    student_df = create_student_analysis(df)
    student = student_df[student_df["USN"] == usn]

    if student.empty:
        return redirect(url_for("dashboard"))

    student = student.iloc[0]
    marks_df = df[df["USN"] == usn].copy()
    marks_df["Status"] = marks_df["Marks"].apply(
        lambda value: "PASS" if value >= PASS_MARK else "FAIL"
    )

    token = insights.save_share_card(
        {
            "name": student["Name"],
            "usn": student["USN"],
            "rank": int(student["Rank"]),
            "total": float(student["Total"]),
            "average": float(student["Average"]),
            "percentage": float(student["Percentage"]),
            "result": student["Result"],
            "failed": int(student["Failed Subjects"]),
            "passed": int(student["Passed Subjects"]),
            "marks": marks_df.to_dict(orient="records"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": session.get("user"),
        }
    )
    return redirect(url_for("report_card", token=token))


@app.route("/card/<token>")
def report_card(token):

    card = insights.get_share_card(token)

    if not card:
        return render_template("report_card.html", missing=True), 404

    public_url = request.url
    return render_template(
        "report_card.html",
        missing=False,
        card=card,
        public_url=public_url,
        qr_svg=insights.qr_svg(public_url),
        pass_mark=PASS_MARK,
    )

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    os.makedirs(
        UPLOAD_FOLDER,
        exist_ok=True
    )

    app.run(
        debug=True
    )
