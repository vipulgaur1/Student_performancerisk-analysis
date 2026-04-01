from flask import Blueprint, render_template, abort, redirect, url_for, session
from database.db import get_db
import json
from datetime import datetime

views_bp = Blueprint('views', __name__)

# ── Teacher overview dashboard (existing) ────────────────────────────────────
@views_bp.route('/')
def dashboard():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT id, name, branch, predicted_category, confidence
        FROM students ORDER BY created_at DESC
    """)
    students = cur.fetchall()
    cur.execute("""
        SELECT predicted_category, COUNT(*) as cnt FROM students
        WHERE predicted_category IS NOT NULL GROUP BY predicted_category
    """)
    counts_raw = cur.fetchall()
    counts = {'Weak': 0, 'Average': 0, 'Advanced': 0}
    for row in counts_raw:
        if row['predicted_category'] in counts:
            counts[row['predicted_category']] = row['cnt']
    return render_template('dashboard.html', students=students, counts=counts)


# ── Student-facing dashboard ──────────────────────────────────────────────────
@views_bp.route('/dashboard/<student_id>')
def student_dashboard(student_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    s = cur.fetchone()
    if not s:
        abort(404)

    cat    = s['predicted_category'] or 'Unknown'
    status = "At Risk" if cat == 'Weak' else ("Safe" if cat == 'Advanced' else "Monitor")

    overall = round(
        float(s['attendance'] or 0)           * 0.30 +
        float(s['assignment_completion'] or 0) * 0.25 +
        float(s['mid_term_marks'] or 0)        * 0.25 +
        float(s['quiz_avg_score'] or 0)        * 0.20, 1
    )

    prev_gpa   = float(s['previous_sem_gpa'] or 0)
    perf_delta = (overall - 60) / 100 * 0.5
    pred_cgpa  = round(max(0.0, min(10.0, prev_gpa + perf_delta)), 2)

    dropout_prob = round(max(0.0, min(99.0,
        (75  - float(s['attendance'] or 0))           * 0.5 +
        (70  - float(s['assignment_completion'] or 0)) * 0.3 +
        (60  - float(s['mid_term_marks'] or 0))        * 0.2
    )), 1)

    data = {
        "name":             s['name'],
        "id":               s['id'],
        "branch":           s['branch'] or "B.Tech",
        "semester":         f"Semester {s['semester']}" if s['semester'] else "—",
        "dropout_prob":     dropout_prob,
        "predicted_cgpa":   pred_cgpa,
        "overall_score":    overall,
        "status":           status,
        "model_conf":       round(float(s['confidence'] or 0), 1),
        "attendance":       round(float(s['attendance'] or 0), 1),
        "assignment_score": round(float(s['assignment_completion'] or 0), 1),
        "marks":            round(float(s['mid_term_marks'] or 0), 1),
        "participation":    {0: 20, 1: 55, 2: 90}.get(int(s['class_participation'] or 0), 20),
        "backlogs":         int(s['backlogs'] or 0),
        "punctuality":      max(0, 100 - int(s['assignment_delay'] or 0) * 10),
        "rank":             "—",
        "class_size":       "—",
        "shap_values":      _build_shap_values(s),
        "recommendations":  _build_recommendations(s),
        "last_updated":     datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "radar": [
            {"subject": "Attendance",    "A": round(float(s['attendance'] or 0), 1)},
            {"subject": "Assignments",   "A": round(float(s['assignment_completion'] or 0), 1)},
            {"subject": "Mid-term",      "A": round(float(s['mid_term_marks'] or 0), 1)},
            {"subject": "Participation", "A": {0: 20, 1: 55, 2: 90}.get(int(s['class_participation'] or 0), 20)},
            {"subject": "CGPA Trend",    "A": round(min(pred_cgpa / 10 * 100, 100), 1)},
            {"subject": "Punctuality",   "A": max(0, 100 - int(s['assignment_delay'] or 0) * 10)},
        ],
    }
    return render_template('student_dashboard.html', student_json=json.dumps(data))


# ── Stub routes so sidebar links don't 404 ───────────────────────────────────
@views_bp.route('/leaderboard')
def leaderboard():
    # TODO: build leaderboard template
    return "<h2 style='color:white;background:#0d1117;padding:40px'>Leaderboard — Coming Soon</h2>"

@views_bp.route('/timetable')
def timetable():
    return "<h2 style='color:white;background:#0d1117;padding:40px'>Timetable — Coming Soon</h2>"

@views_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('views.dashboard'))


# ── Keep your existing routes ─────────────────────────────────────────────────
@views_bp.route('/student/add')
def add_student_form():
    return render_template('add_student.html')

@views_bp.route('/student/<student_id>')
def student_detail(student_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = cur.fetchone()
    if not student:
        abort(404)
    return render_template('student_detail.html', student=student)

@views_bp.route('/remedial/<student_id>')
def remedial_page(student_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = cur.fetchone()
    return render_template('remedial.html', student=student)

@views_bp.route('/tips')
def tips_page():
    return render_template('tips.html')


# ── Keep your helper functions exactly as they are ───────────────────────────
def _level_to_pct(level):
    return {0: 20, 1: 55, 2: 90}.get(int(level or 0), 20)

def _build_shap_values(s):
    shap = []
    att = float(s['attendance'] or 0)
    shap.append({"feature": "Attendance", "shap": round((75 - att) / 25 * 2.5, 3) if att < 75 else round((att - 75) / 25 * 1.5, 3), "raw": f"{att:.0f}%", "direction": "neg" if att < 75 else "pos"})
    asgn = float(s['assignment_completion'] or 0)
    shap.append({"feature": "Assignment Score", "shap": round((70 - asgn) / 70 * 2.0, 3) if asgn < 70 else round((asgn - 70) / 30 * 1.2, 3), "raw": f"{asgn:.0f}/100", "direction": "neg" if asgn < 70 else "pos"})
    mid = float(s['mid_term_marks'] or 0)
    shap.append({"feature": "Mid-term Marks", "shap": round((60 - mid) / 60 * 1.8, 3) if mid < 60 else round((mid - 60) / 40 * 1.0, 3), "raw": f"{mid:.0f}/100", "direction": "neg" if mid < 60 else "pos"})
    part = int(s['class_participation'] or 0)
    shap.append({"feature": "Participation", "shap": round((2 - part) / 2 * 1.2, 3), "raw": {0: "Low", 1: "Medium", 2: "High"}.get(part, "Low"), "direction": "neg" if part < 2 else "pos"})
    gpa = float(s['previous_sem_gpa'] or 0)
    shap.append({"feature": "Prev. GPA", "shap": round(abs(gpa - 7.0) / 10 * 0.9, 3), "raw": str(gpa), "direction": "pos" if gpa >= 7.0 else "neg"})
    delay = float(s['assignment_delay'] or 0)
    shap.append({"feature": "Assignment Delay", "shap": round(min(delay / 7 * 0.8, 0.8), 3), "raw": f"{delay:.0f} days", "direction": "neg" if delay > 0 else "pos"})
    bl = int(s['backlogs'] or 0)
    shap.append({"feature": "Backlogs", "shap": round(min(bl * 0.3, 0.9), 3), "raw": str(bl), "direction": "neg" if bl > 0 else "pos"})
    shap.sort(key=lambda x: x['shap'], reverse=True)
    return shap

def _build_recommendations(s):
    recs = []
    if float(s['attendance'] or 0) < 75:
        recs.append({"icon": "📅", "title": "Boost Attendance Immediately", "priority": "critical", "detail": f"Your attendance is {float(s['attendance']):.0f}% — below the 75% threshold for exam eligibility."})
    if float(s['assignment_completion'] or 0) < 60:
        recs.append({"icon": "📝", "title": "Submit Overdue Assignments", "priority": "high", "detail": f"Assignment completion of {float(s['assignment_completion']):.0f}% is low."})
    if float(s['mid_term_marks'] or 0) < 60:
        recs.append({"icon": "📚", "title": "Improve Mid-term Performance", "priority": "high", "detail": f"Scoring {float(s['mid_term_marks']):.0f}/100 is below the class average."})
    if int(s['class_participation'] or 0) < 1:
        recs.append({"icon": "🙋", "title": "Increase Class Participation", "priority": "medium", "detail": "Active participation is a positive ML signal."})
    if int(s['backlogs'] or 0) > 0:
        recs.append({"icon": "📌", "title": "Clear Your Backlogs", "priority": "high", "detail": f"You have {s['backlogs']} active backlog(s)."})
    recs.append({"icon": "👨‍🏫", "title": "Schedule a Mentor Meeting", "priority": "medium", "detail": "Book a 1-on-1 with your faculty mentor this week."})
    return recs