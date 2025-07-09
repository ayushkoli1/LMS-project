from flask import Flask, request, redirect, url_for, render_template, session, send_file
import pandas as pd
import os
import io
import random
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return redirect(url_for('login'))

# ------------------------ Signup ------------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].strip().lower()
        password = request.form['password']
        role = request.form['role']
        background = request.form['background']

        # CAPTCHA temporarily removed

        new_user = {
            "Name": name, "Email": email, "Password": password,
            "Role": role, "Background": background
        }

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'users.xlsx')

        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            df['Email'] = df['Email'].str.lower().str.strip()
            if email in df['Email'].values:
                return render_template('signup.html', error="Email already registered.")
            df = pd.concat([df, pd.DataFrame([new_user])], ignore_index=True)
        else:
            df = pd.DataFrame([new_user])
        df.to_excel(file_path, index=False)

        return redirect(url_for('login'))

    return render_template('signup.html')

# ------------------------ Login ------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form['role'].strip().lower()
        username = request.form['username'].strip().lower()
        password = request.form['password'].strip()
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'users.xlsx')

        df = pd.read_excel(file_path)
        df['Email'] = df['Email'].str.strip().str.lower()
        df['Password'] = df['Password'].astype(str).str.strip()
        df['Role'] = df['Role'].str.strip().str.lower()

        matched_user = df[
            (df['Email'] == username) &
            (df['Password'] == password) &
            (df['Role'] == role)
        ]

        if not matched_user.empty:
            session['user'] = matched_user.iloc[0]['Name']
            session['email'] = username
            session['role'] = role
            session['background'] = matched_user.iloc[0].get('Background', 'Non-IT')

            if role == 'student':
                quiz_file = os.path.join(app.config['UPLOAD_FOLDER'], 'quiz_results.xlsx')
                if os.path.exists(quiz_file):
                    quiz_df = pd.read_excel(quiz_file)
                    quiz_df['Email'] = quiz_df['Email'].str.strip().str.lower()
                    if username not in quiz_df['Email'].values:
                        return redirect(url_for('quiz'))
                else:
                    return redirect(url_for('quiz'))

                return redirect(url_for('student_dashboard'))

            elif role == 'instructor':
                return redirect(url_for('instructor_dashboard'))

        return render_template('login.html', error="Invalid credentials or role.")
    return render_template('login.html')

# ------------------------ Forgot Password ------------------------
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'users.xlsx')
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        new_password = request.form['new_password'].strip()

        # CAPTCHA temporarily removed

        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            df['Email'] = df['Email'].str.lower().str.strip()
            if email in df['Email'].values:
                df.loc[df['Email'] == email, 'Password'] = new_password
                df.to_excel(file_path, index=False)
                return redirect(url_for('login'))
            else:
                return render_template('forgot_password.html', error="Email not found.")
        return "User data file not found."

    return render_template('forgot_password.html')

# ------------------------ Logout ------------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ------------------------ Student Dashboard ------------------------
@app.route('/student_dashboard')
def student_dashboard():
    if session.get('role') != 'student':
        return "Access Denied", 403

    email = session.get('email')
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'quiz_results.xlsx')

    quizzes_taken = 0
    avg_score = 0
    percent_complete = 0

    if os.path.exists(file_path):
        df = pd.read_excel(file_path)
        df['Email'] = df['Email'].str.lower().str.strip()
        student_data = df[df['Email'] == email]

        if not student_data.empty:
            quizzes_taken = len(student_data)
            avg_score = student_data['Percentage'].mean()
            percent_complete = min(avg_score, 100)

    progress = {
        "quizzes_taken": quizzes_taken,
        "avg_score": round(avg_score, 2),
        "percent_complete": round(percent_complete, 2)
    }

    # Dummy deadlines
    deadlines = [
        {"name": "Assignment 1", "due": "2025-07-10", "status": "Pending"},
        {"name": "Quiz 2", "due": "2025-07-15", "status": "Upcoming"}
    ]

    # Gamification logic (replace with real logic if needed)
    gamification = {
        "level": 5,
        "xp": 150,
        "xp_needed": 200,
        "percent_to_next_level": int((150 / 200) * 100),
        "streak_days": 3
    }

    badges = [
        {"name": "First Quiz", "icon_url": "/static/badges/first_quiz.png"},
        {"name": "80% Club", "icon_url": "/static/badges/80plus.png"}
    ]

    return render_template("student_dashboard.html",
                           user=session.get('user'),
                           deadlines=deadlines,
                           progress=progress,
                           gamification=gamification,
                           badges=badges)
# ------------------------ Quiz ------------------------
@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    quiz_file = 'quiz_questions.json'
    result_file = os.path.join(app.config['UPLOAD_FOLDER'], 'quiz_results.xlsx')
    email = session.get('email')
    name = session.get('user')
    background = session.get('background', 'Non-IT')

    if request.method == 'POST':
        data = request.form
        with open(quiz_file, 'r') as f:
            questions = json.load(f)
        question_set = questions['IT'] if background == 'IT' else questions['Non-IT']

        correct = sum(1 for i, q in enumerate(question_set[:10]) if data.get(f'q{i}') == q['answer'])
        total = len(question_set[:10])
        percentage = (correct / total) * 100

        level = "Beginner"
        if percentage >= 80:
            level = "Advanced"
        elif percentage >= 50:
            level = "Intermediate"

        record = {
            "Name": name, "Email": email, "Background": background,
            "Score": correct, "Total": total, "Percentage": percentage,
            "Level": level, "DateTime": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        df = pd.read_excel(result_file) if os.path.exists(result_file) else pd.DataFrame()
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        df.to_excel(result_file, index=False)

        return render_template('result.html', level=level, score=correct, total=total, background=background)

    with open(quiz_file, 'r') as f:
        questions = json.load(f)

    selected_questions = questions['IT'] if background == 'IT' else questions['Non-IT']
    random.shuffle(selected_questions)
    return render_template('quiz.html', questions=selected_questions[:10], background=background)

# ------------------------ Quiz History ------------------------
@app.route('/quiz_history')
def quiz_history():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    result_path = os.path.join(app.config['UPLOAD_FOLDER'], 'quiz_results.xlsx')
    email = session.get('email')

    if os.path.exists(result_path):
        df = pd.read_excel(result_path)
        df = df[df['Email'].str.lower().str.strip() == email]
        df = df.sort_values(by='DateTime', ascending=False)
        return render_template('quiz_history.html', records=df.to_dict(orient='records'))

    return render_template('quiz_history.html', records=[])

# ------------------------ Profile ------------------------
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'users.xlsx')
    email = session.get('email')

    if os.path.exists(file_path):
        df = pd.read_excel(file_path)
        df['Email'] = df['Email'].str.strip().str.lower()
        user_row = df[df['Email'] == email]

        if user_row.empty:
            return "User not found."

        index = user_row.index[0]
        if request.method == 'POST':
            df.at[index, 'Name'] = request.form['name']
            df.at[index, 'Password'] = request.form['password']
            df.at[index, 'Background'] = request.form['background']
            session['user'] = df.at[index, 'Name']
            session['background'] = df.at[index, 'Background']
            df.to_excel(file_path, index=False)

        return render_template('profile.html', user=df.loc[index].to_dict())

    return "User data file not found."

# ------------------------ Browse Courses ------------------------
@app.route('/courses')
def browse_courses():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    default_courses = [
        {"title": "Introduction to Python", "description": "Learn the basics of Python programming"},
        {"title": "Web Development with Flask", "description": "Build web apps using Flask"},
        {"title": "Database Design", "description": "Master SQL and ER diagrams"}
    ]

    dynamic_courses = []
    if os.path.exists('courses.xlsx'):
        df = pd.read_excel('courses.xlsx')
        dynamic_courses = df.to_dict(orient='records')

    all_courses = default_courses + dynamic_courses
    return render_template('courses.html', courses=all_courses)

# ------------------------ Enroll in Course ------------------------
@app.route('/enroll/<course_title>')
def enroll(course_title):
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'enrollments.xlsx')
    record = {
        "Student": session.get('user'),
        "Email": session.get('email'),
        "Course": course_title,
        "DateTime": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    df = pd.read_excel(file_path) if os.path.exists(file_path) else pd.DataFrame()
    df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    df.to_excel(file_path, index=False)

    return redirect(url_for('browse_courses'))

# ------------------------ Instructor Dashboard ------------------------
@app.route('/instructor_dashboard')
def instructor_dashboard():
    if session.get('role') != 'instructor':
        return "Access denied", 403

    default_courses = [
        {"title": "Introduction to Python", "description": "Learn the basics of Python programming"},
        {"title": "Web Development with Flask", "description": "Build web apps using Flask"},
        {"title": "Database Design", "description": "Master SQL and ER diagrams"}
    ]

    dynamic_courses = []
    if os.path.exists('courses.xlsx'):
        df = pd.read_excel('courses.xlsx')
        dynamic_courses = df.to_dict(orient='records')

    all_courses = default_courses + dynamic_courses
    return render_template('instructor_dashboard.html', courses=all_courses, total=len(all_courses))
#---------------------export users-----------------------------------
@app.route('/export_users')
def export_users():
    if session.get('role') != 'instructor':
        return "Access Denied", 403

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'users.xlsx')
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "User data file not found.", 404

# ------------------------ Create Course ------------------------
@app.route('/create_course', methods=['GET', 'POST'])
def create_course():
    if session.get('role') != 'instructor':
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        path = 'courses.xlsx'
        df = pd.read_excel(path) if os.path.exists(path) else pd.DataFrame(columns=['title', 'description'])
        df = pd.concat([df, pd.DataFrame([{'title': title, 'description': description}])], ignore_index=True)
        df.to_excel(path, index=False)

        return redirect(url_for('instructor_dashboard'))

    return render_template('create_course.html')
# ------------------------ Enrollments ------------------------
@app.route('/my_enrollments')
def my_enrollments():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'enrollments.xlsx')
    email = session.get('email')
    records = []
    if os.path.exists(file_path):
        df = pd.read_excel(file_path)
        df['Email'] = df['Email'].str.lower().str.strip()
        student_courses = df[df['Email'] == email]
        records = student_courses.to_dict(orient='records')
    return render_template('enrollments.html', records=records)

# ------------------------ My Level ------------------------
@app.route('/my_level')
def my_level():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'quiz_results.xlsx')
    email = session.get('email')
    level = None
    if os.path.exists(file_path):
        df = pd.read_excel(file_path)
        df['Email'] = df['Email'].str.lower().str.strip()
        student_data = df[df['Email'] == email]
        if not student_data.empty:
            latest = student_data.sort_values(by="DateTime", ascending=False).iloc[0]
            level = latest.get("Level")
    return render_template("my_level.html", level=level)

# ------------------------ Skill Suggestions ------------------------
@app.route('/skill_suggestions')
def skill_suggestions():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'quiz_results.xlsx')
    email = session.get('email')
    suggestions = []
    if os.path.exists(file_path):
        df = pd.read_excel(file_path)
        df['Email'] = df['Email'].str.lower().str.strip()
        user_data = df[df['Email'] == email]
        if not user_data.empty:
            latest = user_data.sort_values(by='DateTime', ascending=False).iloc[0]
            level = latest.get('Level')
            if level == 'Beginner':
                suggestions = ['Learn Python Basics', 'Practice Logical Thinking']
            elif level == 'Intermediate':
                suggestions = ['Learn Flask', 'Work on Projects']
            elif level == 'Advanced':
                suggestions = ['Explore Machine Learning', 'Contribute to Open Source']
    return render_template('skill_suggestions.html', suggestions=suggestions)

# ------------------------ View Assignments ------------------------
@app.route('/view_assignments')
def view_assignments():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    assignment_file = os.path.join(app.config['UPLOAD_FOLDER'], 'assignments.xlsx')
    assignments = []
    if os.path.exists(assignment_file):
        df = pd.read_excel(assignment_file)
        assignments = df.to_dict(orient='records')
    return render_template('view_assignments.html', assignments=assignments)

# ------------------------ Download Assignment File ------------------------
@app.route('/download_assignment/<filename>')
def download_assignment(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return "File not found", 404

# ------------------------ View Announcements ------------------------
@app.route('/view_announcements')
def view_announcements():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    announcement_file = os.path.join(app.config['UPLOAD_FOLDER'], 'announcements.xlsx')
    announcements = []
    if os.path.exists(announcement_file):
        df = pd.read_excel(announcement_file)
        df = df.sort_values(by='Date', ascending=False)
        announcements = df.to_dict(orient='records')
    return render_template('view_announcements.html', announcements=announcements)
# ------------------------ Ask a Doubt ------------------------
@app.route('/ask_doubt', methods=['GET', 'POST'])
def ask_doubt():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    if request.method == 'POST':
        doubt = request.form.get('doubt')
        name = session.get('user')
        email = session.get('email')

        # Save doubt to a file (or database)
        doubt_record = {
            'Name': name,
            'Email': email,
            'Doubt': doubt,
            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        doubt_file = os.path.join(app.config['UPLOAD_FOLDER'], 'doubts.xlsx')
        df = pd.read_excel(doubt_file) if os.path.exists(doubt_file) else pd.DataFrame()
        df = pd.concat([df, pd.DataFrame([doubt_record])], ignore_index=True)
        df.to_excel(doubt_file, index=False)

        return render_template('ask_doubt.html', message="Your doubt has been submitted.")
    return render_template('ask_doubt.html')

# ------------------------ Feedback ------------------------
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    feedback_file = os.path.join(app.config['UPLOAD_FOLDER'], 'feedback.xlsx')
    email = session.get('email')
    name = session.get('user')

    if request.method == 'POST':
        rating = request.form.get('rating')
        comments = request.form.get('comments')

        record = {
            "Name": name,
            "Email": email,
            "Rating": rating,
            "Comments": comments,
            "DateTime": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        df = pd.read_excel(feedback_file) if os.path.exists(feedback_file) else pd.DataFrame()
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        df.to_excel(feedback_file, index=False)

        return redirect(url_for('student_dashboard'))

    return render_template('feedback.html')

# ------------------------ Leaderboard ------------------------
@app.route('/leaderboard')
def leaderboard():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'quiz_results.xlsx')
    leaderboard_data = []

    if os.path.exists(file_path):
        df = pd.read_excel(file_path)
        df['Email'] = df['Email'].str.lower().str.strip()
        grouped = df.groupby('Email').agg({
            'Name': 'first',
            'Score': 'sum',
            'Total': 'sum'
        }).reset_index()
        grouped['Percentage'] = (grouped['Score'] / grouped['Total']) * 100
        leaderboard_data = grouped.sort_values(by='Percentage', ascending=False).to_dict(orient='records')

    return render_template('leaderboard.html', leaderboard=leaderboard_data)
# -------------------------------- Run App -----------------------------
if __name__ == '__main__':
    app.run(debug=True)
