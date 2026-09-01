from flask import Flask, render_template, request, redirect, url_for, session, send_file
import pandas as pd
import os
import plotly.graph_objs as go
import plotly.offline as pyo
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ---------------- LOGIN ----------------
ADMIN_USERNAME = 'HOD'
ADMIN_PASSWORD = 'HODCSE123'


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['user'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid Username or Password')
    return render_template('login.html')


# ---------------- MAIN PAGE ----------------
@app.route('/index', methods=['GET', 'POST'])
def index():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('index.html', error="No file uploaded")

        file = request.files['file']
        if file.filename == '':
            return render_template('index.html', error="No file selected")

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded_data.xlsx')
        file.save(filepath)
        session['uploaded_file'] = filepath
        return redirect(url_for('dashboard'))

    return render_template('index.html')


# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    if 'uploaded_file' not in session:
        return redirect(url_for('index'))

    filepath = session['uploaded_file']

    try:
        df = pd.read_excel(filepath)
        required_columns = ['Name', 'USN', 'Subject Name', 'Subject Code', 'Marks']

        for col in required_columns:
            if col not in df.columns:
                return render_template('index.html', error=f"Missing column: {col}")

        df['Marks'] = pd.to_numeric(df['Marks'], errors='coerce')
        df.dropna(subset=['Marks'], inplace=True)

        # Subject-level analysis
        analysis_data = []
        for subject, group in df.groupby('Subject Name'):
            avg = round(group['Marks'].mean(), 2)
            high = int(group['Marks'].max())
            low = int(group['Marks'].min())
            pass_count = (group['Marks'] >= 35).sum()
            fail_count = (group['Marks'] < 35).sum()
            analysis_data.append({
                'subject_name': subject,
                'average': avg,
                'highest': high,
                'lowest': low,
                'pass': pass_count,
                'fail': fail_count
            })

        # ---------------- BASIC CHARTS ----------------
        total_pass = (df['Marks'] >= 35).sum()
        total_fail = (df['Marks'] < 35).sum()

        pie_fig = go.Figure(data=[go.Pie(labels=['Pass', 'Fail'], values=[total_pass, total_fail], hole=.3)])
        pie_fig.update_layout(title='Overall Pass vs Fail')
        pie_chart = pyo.plot(pie_fig, output_type='div')

        avg_marks = df.groupby('Subject Name')['Marks'].mean().reset_index()
        bar_fig = go.Figure([go.Bar(x=avg_marks['Subject Name'], y=avg_marks['Marks'], marker_color='blue')])
        bar_fig.update_layout(title='Average Marks per Subject', xaxis_title='Subject', yaxis_title='Average Marks')
        graphs = [pyo.plot(bar_fig, output_type='div')]

        # ---------------- ADVANCED STUDENT ANALYTICS ----------------
        # 1️⃣ Performance Pyramid
        performance_levels = {
            'Excellent (85-100)': ((df['Marks'] >= 85) & (df['Marks'] <= 100)).sum(),
            'Good (70-84)': ((df['Marks'] >= 70) & (df['Marks'] < 85)).sum(),
            'Average (50-69)': ((df['Marks'] >= 50) & (df['Marks'] < 70)).sum(),
            'Poor (35-49)': ((df['Marks'] >= 35) & (df['Marks'] < 50)).sum(),
            'Fail (<35)': (df['Marks'] < 35).sum()
        }
        pyramid_fig = go.Figure(go.Funnel(
            y=list(performance_levels.keys())[::-1],
            x=list(performance_levels.values())[::-1],
            marker={'color': ['#0074D9', '#39CCCC', '#3D9970', '#FF851B', '#FF4136']}
        ))
        pyramid_fig.update_layout(title='Student Performance Pyramid')
        pyramid_chart = pyo.plot(pyramid_fig, output_type='div')

        # 2️⃣ Top 5 Students - Triangle Chart + Marks Distribution
        top_students = df.groupby('Name')['Marks'].mean().reset_index().sort_values(by='Marks', ascending=False).head(5)

        # Triangle-like pyramid graph
        top_fig = go.Figure(go.Funnel(
            y=top_students['Name'][::-1],
            x=top_students['Marks'][::-1],
            textinfo="value+percent initial",
            marker={'color': ['#001f3f', '#0074D9', '#39CCCC', '#3D9970', '#2ECC40']}
        ))
        top_fig.update_layout(title='Top 5 Students Pyramid', title_font=dict(size=20))
        top_chart = pyo.plot(top_fig, output_type='div')

        # Marks Distribution
        dist_fig = go.Figure([go.Histogram(x=df['Marks'], nbinsx=10)])
        dist_fig.update_layout(title='Marks Distribution', xaxis_title='Marks', yaxis_title='Count')
        dist_chart = pyo.plot(dist_fig, output_type='div')

        # 3️⃣ Box Plot - Spread of student marks
        box_fig = go.Figure()
        for student in df['Name'].unique():
            student_marks = df[df['Name'] == student]['Marks']
            box_fig.add_trace(go.Box(y=student_marks, name=student))
        box_fig.update_layout(title='Student Marks Distribution', yaxis_title='Marks')
        box_chart = pyo.plot(box_fig, output_type='div')

        # 4️⃣ Radar Chart - Top 3 students comparison
        top3 = top_students.head(3)
        radar_fig = go.Figure()
        subjects = df['Subject Name'].unique()
        for student in top3['Name']:
            student_avg = []
            for subj in subjects:
                marks = df[(df['Name'] == student) & (df['Subject Name'] == subj)]['Marks'].mean()
                student_avg.append(marks if pd.notna(marks) else 0)
            radar_fig.add_trace(go.Scatterpolar(r=student_avg, theta=subjects, fill='toself', name=student))
        radar_fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                                title="Top 3 Student Radar Comparison")
        radar_chart = pyo.plot(radar_fig, output_type='div')

        # Combine all extra charts
        extra_graphs = [pyramid_chart, top_chart, dist_chart, box_chart, radar_chart]

        return render_template(
            'index.html',
            analysis=analysis_data,
            pie_chart=pie_chart,
            graphs=graphs,
            extra_graphs=extra_graphs
        )

    except Exception as e:
        print("Error in dashboard:", e)
        return render_template('index.html', error="Error processing Excel file.")


# ---------------- DOWNLOAD ----------------
@app.route('/download')
def download_report():
    if 'uploaded_file' not in session:
        return redirect(url_for('index'))

    filepath = session['uploaded_file']
    df = pd.read_excel(filepath)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Student Data')
    output.seek(0)
    return send_file(output, download_name="student_analysis_report.xlsx", as_attachment=True)


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------------- RUN APP ----------------
if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)
