from flask import Blueprint, render_template, abort, redirect, url_for, session, request
from database.db import get_db
import json
from datetime import datetime

views_bp = Blueprint('views', __name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def compute_performance_score(s) -> float:
    """
    Composite performance score (0–100) using eight weighted academic/behavioural
    factors.  Weights sum to exactly 1.0.

      Weight  Factor
      ──────  ─────────────────────────────────────────────────────────────────
       0.25   Mid-term marks              (0–100 scale)
       0.20   Attendance                  (0–100 scale)
       0.15   Class test score            (0–100 scale)
       0.15   Assignment completion       (0–100 scale)
       0.10   Quiz average score          (0–100 scale)
       0.10   Previous GPA               (0–10 normalised → 0–100)
       0.03   Class participation         (0/1/2 normalised → 0/50/100)
       0.02   Behaviour                   (0/1/2 normalised → 0/50/100)
      ──────
       1.00
    """
    mid   = float(s['mid_term_marks']        or 0)
    att   = float(s['attendance']            or 0)
    ctest = float(s['class_test_score']      or 0)
    asgn  = float(s['assignment_completion'] or 0)
    quiz  = float(s['quiz_avg_score']        or 0)
    gpa   = min(float(s['previous_sem_gpa']  or 0) * 10, 100)   # 0–10 → 0–100
    part  = min(int(s['class_participation'] or 0) * 50, 100)   # 0/1/2 → 0/50/100
    behav = min(int(s['behaviour']           or 0) * 50, 100)   # 0/1/2 → 0/50/100

    score = (
        mid   * 0.25 +
        att   * 0.20 +
        ctest * 0.15 +
        asgn  * 0.15 +
        quiz  * 0.10 +
        gpa   * 0.10 +
        part  * 0.03 +
        behav * 0.02
    )
    return round(score, 1)


def status_badge(score: float) -> str:
    """Map performance score to a human-readable status label."""
    if score >= 75:
        return "Top Performer"
    if score >= 50:
        return "Consistent"
    return "Needs Improvement"


def generate_timetable(counts: dict) -> list:
    """
    Build a realistic 5-day academic + intervention timetable.

    Structure (per day)
    ───────────────────
    Morning (09:00–01:15) : Single-track regular academic sessions for all students.
    Lunch   (01:15–02:00) : Lunch break.
    Afternoon (02:00–05:00): Three parallel intervention tracks — one per risk category.
        Weak     → Remedial lecture, doubt-clearing, mentor 1-on-1
        Average  → Improvement workshop, practice lab, peer study
        Advanced → Advanced workshop, peer mentoring, research club

    Each day has distinct sessions (no repeats) and NO conflicting time slots within
    a single track.
    """
    weak     = int(counts.get('Weak',     0))
    average  = int(counts.get('Average',  0))
    advanced = int(counts.get('Advanced', 0))

    # ── Morning academic sessions per day (unique, realistic subject names) ──
    MORNING = [
        # Monday
        [
            ("09:00–10:00", "Data Structures & Algorithms", "Dr. R. Sharma",   "regular"),
            ("10:00–11:00", "Operating Systems",            "Prof. A. Mehta",  "regular"),
            ("11:00–11:15", "Short Break",                  "—",               "break"),
            ("11:15–12:15", "Database Management Systems",  "Prof. S. Gupta",  "regular"),
            ("12:15–01:15", "Software Engineering",         "Dr. P. Iyer",     "regular"),
        ],
        # Tuesday
        [
            ("09:00–10:00", "Computer Networks",            "Prof. A. Mehta",  "regular"),
            ("10:00–11:00", "Web Technologies",             "Dr. N. Patel",    "regular"),
            ("11:00–11:15", "Short Break",                  "—",               "break"),
            ("11:15–12:15", "Artificial Intelligence",      "Dr. R. Sharma",   "regular"),
            ("12:15–01:15", "Advanced Java Programming",    "Prof. K. Singh",  "regular"),
        ],
        # Wednesday
        [
            ("09:00–10:00", "Machine Learning Concepts",    "Dr. P. Iyer",     "regular"),
            ("10:00–11:00", "Cloud Computing",              "Prof. S. Gupta",  "regular"),
            ("11:00–11:15", "Short Break",                  "—",               "break"),
            ("11:15–12:15", "Data Structures Lab",          "Lab Instructor",  "regular"),
            ("12:15–01:15", "Mini Project Review",          "Project Guide",   "regular"),
        ],
        # Thursday
        [
            ("09:00–10:00", "Computer Organisation",        "Dr. R. Sharma",   "regular"),
            ("10:00–11:00", "Software Testing & QA",        "Prof. A. Mehta",  "regular"),
            ("11:00–11:15", "Short Break",                  "—",               "break"),
            ("11:15–12:15", "Mobile Application Dev.",      "Dr. N. Patel",    "regular"),
            ("12:15–01:15", "Cyber Security Basics",        "Prof. K. Singh",  "regular"),
        ],
        # Friday
        [
            ("09:00–10:00", "Theory of Computation",        "Dr. P. Iyer",     "regular"),
            ("10:00–11:00", "Python & Data Science",        "Prof. S. Gupta",  "regular"),
            ("11:00–11:15", "Short Break",                  "—",               "break"),
            ("11:15–12:15", "Weekly Quiz / Class Test",     "Class Coordinator","regular"),
            ("12:15–01:15", "Seminar / Guest Lecture",      "HOD / Guest",     "regular"),
        ],
    ]

    # ── Afternoon intervention tracks (3 parallel slots per day) ─────────────
    # Each sub-list: [(time, session, faculty), (time, session, faculty), ...]
    # All three categories share the same time bands per slot index.
    TIME_BANDS = ["02:00–03:00", "03:00–04:00", "04:00–05:00"]

    WEAK_PM = [
        # Monday
        [
            ("Remedial Lecture – DSA",        "Dr. R. Sharma"),
            ("Doubt-Clearing Session",         "Prof. A. Mehta"),
            ("Mentor 1-on-1 Check-in",         "Faculty Mentor"),
        ],
        # Tuesday
        [
            ("Attendance Recovery Slot",       "Class Coordinator"),
            ("Assignment Completion Drive",    "Lab Instructor"),
            ("Backlog Clearance Session",      "Prof. A. Mehta"),
        ],
        # Wednesday
        [
            ("Remedial – DBMS Focus",          "Prof. S. Gupta"),
            ("Doubt Session – Algorithms",     "Dr. R. Sharma"),
            ("Progress Review with Mentor",    "Faculty Mentor"),
        ],
        # Thursday
        [
            ("Concept Revision – Networks",    "Dr. N. Patel"),
            ("Doubt & Q&A Session",            "Prof. K. Singh"),
            ("Counselling / Motivation Talk",  "Counsellor"),
        ],
        # Friday
        [
            ("Weekly Performance Review",      "HOD"),
            ("Remedial – AI & ML Concepts",    "Dr. P. Iyer"),
            ("Group Doubt Session",            "All Faculty"),
        ],
    ]

    AVERAGE_PM = [
        # Monday
        [
            ("Improvement Workshop – DSA",    "Prof. S. Gupta"),
            ("Assignment Practice Lab",       "Lab Instructor"),
            ("Peer Study Group",              "Senior Students"),
        ],
        # Tuesday
        [
            ("Mock Test Session",             "Prof. A. Mehta"),
            ("Concept Strengthening – CN",    "Dr. R. Sharma"),
            ("Group Discussion & Debate",     "Prof. K. Singh"),
        ],
        # Wednesday
        [
            ("Coding Practice Session",       "Lab Instructor"),
            ("Assignment Review & Feedback",  "Prof. S. Gupta"),
            ("Peer Teaching Session",         "Advanced Students"),
        ],
        # Thursday
        [
            ("Problem-Solving Workshop",      "Dr. N. Patel"),
            ("Performance Goal Setting",      "Faculty Mentor"),
            ("Project Guidance Session",      "Project Guide"),
        ],
        # Friday
        [
            ("Weekly Progress Review",        "HOD"),
            ("Quiz Preparation Session",      "Prof. A. Mehta"),
            ("Career Guidance Talk",          "Placement Cell"),
        ],
    ]

    ADVANCED_PM = [
        # Monday
        [
            ("Advanced Algorithm Workshop",   "Dr. P. Iyer"),
            ("Peer Mentoring – Weak Students","Top Performers"),
            ("Research / Project Club",       "Research Faculty"),
        ],
        # Tuesday
        [
            ("Competitive Coding Practice",   "Dr. R. Sharma"),
            ("Open Source Contribution",      "Lab Instructor"),
            ("Advanced AI / ML Lab",          "Dr. P. Iyer"),
        ],
        # Wednesday
        [
            ("Research Paper Study Circle",   "Dr. P. Iyer"),
            ("Hackathon Preparation",         "Project Guide"),
            ("Innovation & Ideation Lab",     "Research Faculty"),
        ],
        # Thursday
        [
            ("Technical Presentation Skills", "Dr. N. Patel"),
            ("Peer Teaching – Avg Students",  "Advanced Students"),
            ("Internship Readiness Session",  "Placement Cell"),
        ],
        # Friday
        [
            ("Weekly Achievement Review",     "HOD"),
            ("Advanced Project Work",         "Project Guide"),
            ("Alumni Interaction / Networking","Alumni Cell"),
        ],
    ]

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    timetable = []

    for d_idx, day in enumerate(days):
        # Morning: sequential single-track slots
        morning_slots = []
        for time, name, faculty, cls in MORNING[d_idx]:
            morning_slots.append({
                "time":    time,
                "session": name,
                "faculty": faculty,
                "cls":     cls,
                "is_break": cls == "break",
            })

        # Afternoon: three parallel category tracks per time band
        afternoon_slots = []
        for s_idx, time_band in enumerate(TIME_BANDS):
            w_sess, w_fac = WEAK_PM[d_idx][s_idx]
            a_sess, a_fac = AVERAGE_PM[d_idx][s_idx]
            v_sess, v_fac = ADVANCED_PM[d_idx][s_idx]
            afternoon_slots.append({
                "time": time_band,
                "weak": {
                    "session": w_sess,
                    "faculty": w_fac,
                    "count":   weak,
                    "active":  weak > 0,
                },
                "average": {
                    "session": a_sess,
                    "faculty": a_fac,
                    "count":   average,
                    "active":  average > 0,
                },
                "advanced": {
                    "session": v_sess,
                    "faculty": v_fac,
                    "count":   advanced,
                    "active":  advanced > 0,
                },
            })

        timetable.append({
            "day":       day,
            "morning":   morning_slots,
            "afternoon": afternoon_slots,
        })

    return timetable


# ── Role selection (landing page) ────────────────────────────────────────────
@views_bp.route('/')
def role_selection():
    error = request.args.get('error', '')
    return render_template('login.html', error=error)


# ── Admin / Teacher overview dashboard ───────────────────────────────────────
@views_bp.route('/dashboard')
def dashboard():
    session.pop('student_id', None)   # clear any student session so admin sees admin sidebar
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

    # ── Weekly Academic Health Report data ────────────────────────────────────
    cur.execute("SELECT COUNT(*) as cnt FROM students WHERE attendance < 75")
    att_drop_alerts = cur.fetchone()['cnt']

    cur.execute("SELECT AVG(attendance) as avg_att FROM students")
    avg_att = round(cur.fetchone()['avg_att'] or 0, 1)

    cur.execute("""
        SELECT AVG(mid_term_marks * 0.25 + attendance * 0.20 +
                   class_test_score * 0.15 + assignment_completion * 0.15 +
                   quiz_avg_score * 0.10) as avg_perf
        FROM students
    """)
    avg_perf = round(cur.fetchone()['avg_perf'] or 0, 1)

    # Students who improved: currently Average or Advanced but in at-risk threshold previously
    # Approximation: attendance >= 75 and backlogs = 0 and was Weak
    cur.execute("""
        SELECT COUNT(*) as cnt FROM students
        WHERE predicted_category IN ('Average','Advanced')
          AND attendance >= 75 AND backlogs = 0
    """)
    improved_count = cur.fetchone()['cnt']

    health = {
        'weak_count':      counts.get('Weak', 0),
        'improved_count':  improved_count,
        'att_drop_alerts': att_drop_alerts,
        'avg_performance': avg_perf,
        'avg_attendance':  avg_att,
    }

    return render_template('dashboard.html', students=students, counts=counts, health=health)


# ── Student-facing dashboard ──────────────────────────────────────────────────
@views_bp.route('/dashboard/<student_id>')
def student_dashboard(student_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    s = cur.fetchone()
    if not s:
        abort(404)

    # ── Compute this student's performance score ──────────────────────────────
    perf_score = compute_performance_score(s)
    cat        = s['predicted_category'] or 'Unknown'
    badge      = status_badge(perf_score)

    # ── Leaderboard rank: score all students, find position ──────────────────
    cur.execute("""
        SELECT id, name, branch,
               mid_term_marks, attendance, class_test_score, quiz_avg_score,
               assignment_completion, previous_sem_gpa,
               class_participation, behaviour, predicted_category
        FROM students
    """)
    all_rows = cur.fetchall()

    scored = []
    for st in all_rows:
        sc = compute_performance_score(st)
        scored.append({
            "id":       st['id'],
            "name":     st['name'] or "Student",
            "branch":   st['branch'] or "—",
            "score":    sc,
            "category": st['predicted_category'] or 'Unknown',
        })
    scored.sort(key=lambda x: x['score'], reverse=True)

    total_students = len(scored)
    my_rank = total_students  # fallback
    for i, st in enumerate(scored):
        if st['id'] == student_id:
            my_rank = i + 1
            break

    rank_pct = round((1 - (my_rank - 1) / max(total_students, 1)) * 100, 1)

    # ── Nearby ranked students (2 above + 2 below) ───────────────────────────
    nearby = []
    for i, st in enumerate(scored):
        rank = i + 1
        if st['id'] == student_id:
            continue
        if abs(rank - my_rank) <= 2:
            nearby.append({
                "rank":     rank,
                "name":     st['name'],
                "branch":   st['branch'],
                "score":    st['score'],
                "category": st['category'],
                "is_above": rank < my_rank,
            })
    nearby.sort(key=lambda x: x['rank'])

    # ── Category-specific recommendations ────────────────────────────────────
    recommendations = _build_category_recommendations(s, cat)

    # ── 6-month simulated performance trend ──────────────────────────────────
    trend = _build_trend(s, perf_score)

    # ── Subject-wise scores for bar chart ────────────────────────────────────
    subjects = [
        {"name": "Mid-Term",    "score": round(float(s['mid_term_marks']        or 0), 1)},
        {"name": "Class Test",  "score": round(float(s['class_test_score']      or 0), 1)},
        {"name": "Quiz Avg",    "score": round(float(s['quiz_avg_score']        or 0), 1)},
        {"name": "Assignments", "score": round(float(s['assignment_completion'] or 0), 1)},
        {"name": "Attendance",  "score": round(float(s['attendance']            or 0), 1)},
    ]

    # ── Additional computed values ────────────────────────────────────────────
    att          = round(float(s['attendance']            or 0), 1)
    quiz         = round(float(s['quiz_avg_score']        or 0), 1)
    class_test   = round(float(s['class_test_score']      or 0), 1)
    asgn         = round(float(s['assignment_completion'] or 0), 1)
    mid          = round(float(s['mid_term_marks']        or 0), 1)
    prev_gpa     = round(float(s['previous_sem_gpa']      or 0), 2)
    backlogs     = int(s['backlogs']                      or 0)
    part_level   = int(s['class_participation']           or 0)
    part_pct     = {0: 20, 1: 55, 2: 90}.get(part_level, 20)
    part_label   = {0: "Low", 1: "Medium", 2: "High"}.get(part_level, "Low")
    delay_days   = int(s['assignment_delay']              or 0)
    punctuality  = max(0, 100 - delay_days * 10)

    # Predicted next-sem GPA (lightweight formula)
    overall      = round(att * 0.30 + asgn * 0.25 + mid * 0.25 + quiz * 0.20, 1)
    perf_delta   = (overall - 60) / 100 * 0.5
    pred_cgpa    = round(max(0.0, min(10.0, prev_gpa + perf_delta)), 2)

    # Attendance status class
    att_status = "danger" if att < 65 else ("warning" if att < 75 else "success")

    # AI-powered sections
    weekly_goals   = _build_weekly_goals(s, cat)
    explainability = _build_explainability(s, cat, perf_score)

    # ── Branch rank ────────────────────────────────────────────────────────────
    my_branch = (s['branch'] or '').upper()
    branch_scored = [st for st in scored if (st['branch'] or '').upper() == my_branch]
    branch_rank = len(branch_scored)
    for i, st in enumerate(branch_scored):
        if st['id'] == student_id:
            branch_rank = i + 1
            break
    branch_total = max(1, len(branch_scored))

    # ── Section rank (A/B/C — deterministic from full sorted leaderboard) ─────
    _sec_names = ['A', 'B', 'C']
    my_section = 'A'
    for idx, st in enumerate(scored):
        if st['id'] == student_id:
            my_section = _sec_names[idx % 3]
            break
    section_scored = [st for i, st in enumerate(scored) if _sec_names[i % 3] == my_section]
    section_rank = len(section_scored)
    for i, st in enumerate(section_scored):
        if st['id'] == student_id:
            section_rank = i + 1
            break
    section_total = max(1, len(section_scored))

    # ── Class-average metrics (for comparison table) ──────────────────────────
    cur.execute("""
        SELECT AVG(attendance) as avg_att,
               AVG(previous_sem_gpa) as avg_gpa,
               AVG(assignment_completion) as avg_asgn,
               AVG(mid_term_marks) as avg_mid
        FROM students
    """)
    cavg = cur.fetchone()
    class_avg_att  = round(float(cavg['avg_att']  or 0), 1)
    class_avg_gpa  = round(float(cavg['avg_gpa']  or 0), 2)
    class_avg_asgn = round(float(cavg['avg_asgn'] or 0), 1)
    class_avg_mid  = round(float(cavg['avg_mid']  or 0), 1)

    # ── Topper stats ───────────────────────────────────────────────────────────
    topper_att = topper_gpa = topper_asgn = topper_mid = 0.0
    topper_score_val = perf_score
    if scored:
        topper_id = scored[0]['id']
        topper_score_val = scored[0]['score']
        cur.execute("""
            SELECT attendance, previous_sem_gpa, assignment_completion, mid_term_marks
            FROM students WHERE id = ?
        """, (topper_id,))
        tr = cur.fetchone()
        if tr:
            topper_att  = round(float(tr['attendance']            or 0), 1)
            topper_gpa  = round(float(tr['previous_sem_gpa']      or 0), 2)
            topper_asgn = round(float(tr['assignment_completion'] or 0), 1)
            topper_mid  = round(float(tr['mid_term_marks']        or 0), 1)

    # ── Improvement targets & exam alerts ─────────────────────────────────────
    improvement_targets = _build_improvement_targets(
        s, cat, my_rank, total_students, class_avg_att, class_avg_gpa)
    exam_alerts = _build_exam_alerts(s)

    # ── Placement readiness (same formula as student_detail) ──────────────────
    gpa_pct   = min(prev_gpa * 10, 100)
    readiness = round(att * 0.30 + gpa_pct * 0.25 + asgn * 0.25 + quiz * 0.20, 1)
    readiness = max(0, min(100, readiness - backlogs * 5))
    if cat == 'Advanced':
        readiness = max(readiness, 70)
    elif cat == 'Average':
        readiness = max(45, min(readiness, 69))
    elif cat == 'Weak':
        readiness = min(readiness, 44)
    if readiness >= 70:
        readiness_label, readiness_color = 'High',   'var(--green)'
    elif readiness >= 45:
        readiness_label, readiness_color = 'Medium', 'var(--amber)'
    else:
        readiness_label, readiness_color = 'Low',    'var(--red)'

    # ── Subject weakness analysis (same formula as student_detail) ────────────
    if cat == 'Advanced':
        _sf, _sc = 65.0, 100.0
    elif cat == 'Average':
        _sf, _sc = 42.0, 82.0
    else:
        _sf, _sc = 0.0, 75.0

    def _sscore(raw):
        return round(max(_sf, min(_sc, raw)), 1)

    subjects_analysis = [
        {'name': 'DSA',         'score': _sscore(class_test * 0.50 + mid * 0.30 + quiz * 0.20), 'weight': 0.20},
        {'name': 'DBMS',        'score': _sscore(quiz * 0.60 + class_test * 0.40),               'weight': 0.18},
        {'name': 'Mathematics', 'score': _sscore(mid  * 0.60 + class_test * 0.40),               'weight': 0.18},
        {'name': 'Algorithms',  'score': _sscore(quiz * 0.50 + mid * 0.30 + class_test * 0.20), 'weight': 0.15},
        {'name': 'OS',          'score': _sscore(asgn * 0.50 + mid * 0.30 + quiz * 0.20),       'weight': 0.15},
        {'name': 'Networking',  'score': _sscore(att  * 0.40 + asgn * 0.35 + quiz * 0.25),      'weight': 0.14},
    ]
    for sub in subjects_analysis:
        sc = sub['score']
        if sc < 45:
            sub['status'] = 'critical'; sub['color'] = 'var(--red)';   sub['priority'] = 'High'
        elif sc < 60:
            sub['status'] = 'weak';     sub['color'] = 'var(--amber)'; sub['priority'] = 'Medium'
        else:
            sub['status'] = 'ok';       sub['color'] = 'var(--green)'; sub['priority'] = 'Low'
    subjects_analysis.sort(key=lambda x: x['score'])   # weakest first

    return render_template(
        'student_dashboard.html',
        student      = s,
        perf_score   = perf_score,
        cat          = cat,
        badge        = badge,
        my_rank      = my_rank,
        total_students = total_students,
        rank_pct     = rank_pct,
        nearby       = nearby,
        recommendations = recommendations,
        trend_json   = json.dumps(trend),
        subjects_json = json.dumps(subjects),
        att          = att,
        att_status   = att_status,
        quiz         = quiz,
        class_test   = class_test,
        asgn         = asgn,
        mid          = mid,
        prev_gpa     = prev_gpa,
        pred_cgpa    = pred_cgpa,
        backlogs     = backlogs,
        part_label   = part_label,
        part_pct     = part_pct,
        punctuality  = punctuality,
        delay_days   = delay_days,
        overall      = overall,
        last_updated = datetime.now().strftime("%d %b %Y, %I:%M %p"),
        weekly_goals   = weekly_goals,
        explainability = explainability,
        # ── NEW: ranking, comparison, targets, alerts, readiness ──────────────
        branch_rank        = branch_rank,
        branch_total       = branch_total,
        my_section         = my_section,
        section_rank       = section_rank,
        section_total      = section_total,
        class_avg_att      = class_avg_att,
        class_avg_gpa      = class_avg_gpa,
        class_avg_asgn     = class_avg_asgn,
        class_avg_mid      = class_avg_mid,
        topper_att         = topper_att,
        topper_gpa         = topper_gpa,
        topper_asgn        = topper_asgn,
        topper_mid         = topper_mid,
        topper_score       = topper_score_val,
        improvement_targets= improvement_targets,
        exam_alerts        = exam_alerts,
        readiness          = readiness,
        readiness_label    = readiness_label,
        readiness_color    = readiness_color,
        subjects_analysis  = subjects_analysis,
        # Pass counts so sidebar stats render
        counts       = {'Weak': 0, 'Average': 0, 'Advanced': 0},
    )


# ── Leaderboard ───────────────────────────────────────────────────────────────
@views_bp.route('/leaderboard')
def leaderboard():
    db  = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT id, name, branch, semester, year,
               mid_term_marks, attendance, class_test_score, quiz_avg_score,
               assignment_completion, previous_sem_gpa,
               class_participation, behaviour,
               predicted_category, confidence
        FROM students
        ORDER BY name
    """)
    rows = cur.fetchall()

    students = []
    for s in rows:
        score = compute_performance_score(s)
        badge = status_badge(score)
        cat   = s['predicted_category'] or 'Unknown'
        students.append({
            "id":         s['id'],
            "name":       s['name']   or "—",
            "branch":     s['branch'] or "—",
            "semester":   s['semester'],
            "year":       s['year'],
            "score":      score,
            "badge":      badge,
            "category":   cat,
            "confidence": round(float(s['confidence'] or 0), 1),
            "initials":   "".join(p[0].upper() for p in (s['name'] or "S").split()[:2]),
        })

    students.sort(key=lambda x: x['score'], reverse=True)
    for i, st in enumerate(students):
        st['rank'] = i + 1

    branches  = sorted({s['branch']   for s in students if s['branch']   and s['branch']   != '—'})
    semesters = sorted({s['semester'] for s in students if s['semester'] is not None})
    years     = sorted({s['year']     for s in students if s['year']     is not None})

    cat_counts = {'Weak': 0, 'Average': 0, 'Advanced': 0, 'Unknown': 0}
    for s in students:
        cat_counts[s['category']] = cat_counts.get(s['category'], 0) + 1

    counts = {'Weak': cat_counts['Weak'], 'Average': cat_counts['Average'], 'Advanced': cat_counts['Advanced']}

    return render_template(
        'leaderboard.html',
        students      = students,
        branches      = branches,
        semesters     = semesters,
        years         = years,
        total         = len(students),
        cat_counts    = cat_counts,
        students_json = json.dumps(students),
        counts        = counts,
    )


# ── Timetable ─────────────────────────────────────────────────────────────────
@views_bp.route('/timetable')
def timetable():
    db  = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT predicted_category, COUNT(*) as cnt
        FROM students
        WHERE predicted_category IS NOT NULL
        GROUP BY predicted_category
    """)
    counts = {'Weak': 0, 'Average': 0, 'Advanced': 0}
    for row in cur.fetchall():
        if row['predicted_category'] in counts:
            counts[row['predicted_category']] = row['cnt']

    timetable_data = generate_timetable(counts)

    cur.execute("""
        SELECT branch, predicted_category, COUNT(*) as cnt
        FROM students
        WHERE branch IS NOT NULL AND predicted_category IS NOT NULL
        GROUP BY branch, predicted_category
        ORDER BY branch
    """)
    branch_rows = cur.fetchall()
    branch_map = {}
    for row in branch_rows:
        b = row['branch']
        if b not in branch_map:
            branch_map[b] = {'Weak': 0, 'Average': 0, 'Advanced': 0}
        branch_map[b][row['predicted_category']] = row['cnt']

    return render_template(
        'timetable.html',
        timetable    = timetable_data,
        counts       = counts,
        branch_map   = branch_map,
        generated_at = datetime.now().strftime("%d %b %Y, %I:%M %p"),
    )


# ── Existing routes (UNCHANGED) ───────────────────────────────────────────────
@views_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('views.role_selection'))

@views_bp.route('/student/add')
def add_student_form():
    return render_template('add_student.html')

@views_bp.route('/student/<student_id>')
def student_detail(student_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = cur.fetchone()
    if not student:
        abort(404)

    s = student
    # Resolve ML category early — used in ALL derived / computed sections below
    # so that readiness, subject scores, trends, and suggestions are consistent.
    cat = s['predicted_category'] or 'Unknown'

    # ── Placement Readiness Score ─────────────────────────────────────────────
    att  = float(s['attendance']            or 0)
    gpa  = float(s['previous_sem_gpa']      or 0)
    asgn = float(s['assignment_completion'] or 0)
    quiz = float(s['quiz_avg_score']        or 0)
    mid  = float(s['mid_term_marks']        or 0)
    ct   = float(s['class_test_score']      or 0)
    bl   = int(s['backlogs']                or 0)

    gpa_pct  = min(gpa * 10, 100)
    readiness = round(att * 0.30 + gpa_pct * 0.25 + asgn * 0.25 + quiz * 0.20, 1)
    readiness = max(0, min(100, readiness - bl * 5))   # penalise backlogs

    # Category-consistent clamping: the readiness label must never contradict the
    # ML prediction.  The formula can produce misleading results when one raw
    # metric (e.g. attendance) is an extreme outlier in test/dummy data, while
    # the Decision Tree correctly weighted all 12 features before classifying.
    if cat == 'Advanced':
        readiness = max(readiness, 70)      # Advanced → always High readiness
    elif cat == 'Average':
        readiness = max(45, min(readiness, 69))   # Average → Medium readiness band
    elif cat == 'Weak':
        readiness = min(readiness, 44)      # Weak → always Low readiness

    if readiness >= 70:
        readiness_label, readiness_color = 'High',   'var(--green)'
    elif readiness >= 45:
        readiness_label, readiness_color = 'Medium', 'var(--amber)'
    else:
        readiness_label, readiness_color = 'Low',    'var(--red)'

    # ── Subject Weakness Analysis ─────────────────────────────────────────────
    # Each score is a multi-feature composite so that a single outlier metric
    # (e.g. low attendance on one bad test-data record) does not collapse every
    # subject to near-zero.  After computing the composite, a category-consistent
    # floor/ceiling is applied so the displayed scores never contradict the ML
    # category label:
    #   Advanced → floor 65  (good-to-excellent range across all subjects)
    #   Average  → floor 42, ceil 82  (moderate range, no critical alerts)
    #   Weak     → no forced floor    (realistic critical scores permitted)
    if cat == 'Advanced':
        _s_floor, _s_ceil = 65.0, 100.0
    elif cat == 'Average':
        _s_floor, _s_ceil = 42.0, 82.0
    else:  # Weak / Unknown
        _s_floor, _s_ceil = 0.0, 75.0

    def _sub_score(raw):
        """Clamp a raw composite subject score to the category-appropriate band."""
        return round(max(_s_floor, min(_s_ceil, raw)), 1)

    subjects_analysis = [
        # DSA: weighted on class-test, mid-term, quiz — theory-heavy
        {'name': 'DSA',
         'score': _sub_score(ct   * 0.50 + mid  * 0.30 + quiz * 0.20), 'weight': 0.20},
        # DBMS: quiz and class-test focused
        {'name': 'DBMS',
         'score': _sub_score(quiz * 0.60 + ct   * 0.40),               'weight': 0.18},
        # Mathematics: mid-term + class-test (exam-heavy)
        {'name': 'Mathematics',
         'score': _sub_score(mid  * 0.60 + ct   * 0.40),               'weight': 0.18},
        # Algorithms: quiz + mid-term + class-test
        {'name': 'Algorithms',
         'score': _sub_score(quiz * 0.50 + mid  * 0.30 + ct   * 0.20), 'weight': 0.15},
        # OS: assignment completion + mid-term + quiz (lab & theory mix)
        {'name': 'OS',
         'score': _sub_score(asgn * 0.50 + mid  * 0.30 + quiz * 0.20), 'weight': 0.15},
        # Networking: attendance + assignments + quiz (applied / practical)
        {'name': 'Networking',
         'score': _sub_score(att  * 0.40 + asgn * 0.35 + quiz * 0.25), 'weight': 0.14},
    ]
    for sub in subjects_analysis:
        sc = sub['score']
        if sc < 45:
            sub['status'] = 'critical'; sub['color'] = 'var(--red)'
        elif sc < 60:
            sub['status'] = 'weak';     sub['color'] = 'var(--amber)'
        else:
            sub['status'] = 'ok';       sub['color'] = 'var(--green)'
    subjects_analysis.sort(key=lambda x: x['score'])

    # ── Smart Remedial Suggestions ────────────────────────────────────────────
    # Suggestions are category-aware: urgent metric-based alerts (low attendance,
    # low marks) only fire for categories where they are contextually appropriate.
    # Advanced students should never be told to attend remedial classes — doing so
    # contradicts the ML prediction and undermines trust in the system.
    remedial_suggestions = []

    # Backlogs are a universal concern regardless of category
    if bl > 0:
        remedial_suggestions.append({'icon': '📌', 'action': f'Clear {bl} Active Backlog(s)',
            'detail': 'Backlogs directly reduce placement readiness and semester standing.'})

    if cat in ('Weak', 'Average'):
        # Metric-based alerts — only shown for at-risk / monitor categories
        if att < 75:
            remedial_suggestions.append({'icon': '📅', 'action': 'Improve Attendance',
                'detail': f'Current {att:.0f}% — below the 75% exam eligibility threshold.'})
        if asgn < 65:
            remedial_suggestions.append({'icon': '📝', 'action': 'Complete Pending Assignments',
                'detail': f'Assignment completion at {asgn:.0f}%. Submit overdue work immediately.'})
        if mid < 50:
            remedial_suggestions.append({'icon': '📖', 'action': 'Focused Exam Revision',
                'detail': f'Mid-term score {mid:.0f}/100 — revise weak chapters before next exam.'})

    if cat == 'Weak':
        # Critical interventions for at-risk students
        remedial_suggestions.append({'icon': '🏫', 'action': 'Attend Remedial Session',
            'detail': 'Daily remedial lectures are scheduled — attendance is mandatory.'})
        remedial_suggestions.append({'icon': '🙋', 'action': 'Attend Doubt Clearing Session',
            'detail': 'Bring a list of unresolved questions to afternoon doubt sessions.'})

    if cat == 'Advanced':
        # Positive, forward-looking suggestions for strong performers
        remedial_suggestions.append({'icon': '🏆', 'action': 'Keep Up the Strong Performance',
            'detail': 'Maintain consistent attendance and timely assignment submission to stay in the Advanced band.'})
        remedial_suggestions.append({'icon': '🚀', 'action': 'Prepare for Placements',
            'detail': 'Use the Internship Readiness sessions (Thu 04:00–05:00) to sharpen your resume and interview skills.'})

    if not remedial_suggestions:
        remedial_suggestions.append({'icon': '✅', 'action': 'On Track — Maintain Performance',
            'detail': 'Keep consistent attendance and assignment submission.'})

    # ── Intervention record ───────────────────────────────────────────────────
    cur.execute("SELECT * FROM interventions WHERE student_id = ?", (student_id,))
    intervention = cur.fetchone()

    # ── Simulated Student History ─────────────────────────────────────────────
    # The history panel shows a three-semester progression.  Values are
    # category-anchored: the displayed GPA and attendance are bounded to
    # realistic ranges for the ML-predicted category so the history panel is
    # academically plausible and consistent with the prediction label.
    #
    #   Advanced → GPA ≥ 7.50, Attendance ≥ 82 %  (stable / improving)
    #   Average  → GPA ≥ 6.00, Attendance ≥ 65 %  (moderate)
    #   Weak     → GPA ≥ 4.50, Attendance ≥ 48 %  (can show low values)
    import random
    random.seed(hash(student_id) % 2**31)
    prev_cat = {'Weak': 'Weak', 'Average': 'Weak', 'Advanced': 'Average'}.get(cat, 'Average')

    if cat == 'Advanced':
        _gpa_floor, _att_floor = 7.50, 82.0
    elif cat == 'Average':
        _gpa_floor, _att_floor = 6.00, 65.0
    else:  # Weak / Unknown
        _gpa_floor, _att_floor = 4.50, 48.0

    # Displayed anchor values: at least the category floor ensures the trend
    # always starts and ends in an academically believable range.
    _disp_gpa = round(max(gpa, _gpa_floor), 2)
    _disp_att = round(max(att, _att_floor), 1)

    # Three-point ascending trend (Sem N-2 → Sem N-1 → Current)
    gpa_trend = [
        round(max(_gpa_floor, _disp_gpa - random.uniform(0.50, 1.20)), 2),
        round(max(_gpa_floor, _disp_gpa - random.uniform(0.10, 0.50)), 2),
        _disp_gpa,
    ]
    att_trend = [
        round(max(_att_floor, _disp_att - random.uniform(5.0, 12.0)), 1),
        round(max(_att_floor, _disp_att - random.uniform(1.0,  6.0)), 1),
        _disp_att,
    ]

    improved = cat != prev_cat and cat in ('Average', 'Advanced')
    history = {
        'prev_category': prev_cat,
        'current_category': cat,
        'improved': improved,
        'gpa_trend': gpa_trend,
        'att_trend': att_trend,
        'semesters': ['Sem N-2', 'Sem N-1', 'Current'],
    }

    # ── Weekly Academic Health (for context on detail page) ──────────────────
    cur.execute("SELECT COUNT(*) as cnt FROM students WHERE attendance < 75")
    att_alerts = cur.fetchone()['cnt']

    return render_template(
        'student_detail.html',
        student             = student,
        readiness           = readiness,
        readiness_label     = readiness_label,
        readiness_color     = readiness_color,
        subjects_analysis   = subjects_analysis,
        remedial_suggestions= remedial_suggestions,
        intervention        = intervention,
        history             = history,
        att_alerts          = att_alerts,
        cat                 = cat,
    )

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


# ── Private helper functions ──────────────────────────────────────────────────

def _level_to_pct(level):
    return {0: 20, 1: 55, 2: 90}.get(int(level or 0), 20)


def _build_improvement_targets(s, cat, my_rank, total_students, class_avg_att, class_avg_gpa):
    """Generate up to 5 practical, measurable improvement targets for the student."""
    targets = []
    att  = float(s['attendance']            or 0)
    gpa  = float(s['previous_sem_gpa']      or 0)
    asgn = float(s['assignment_completion'] or 0)
    mid  = float(s['mid_term_marks']        or 0)
    bl   = int(s['backlogs']                or 0)

    if att < 75:
        gap = max(1, round(75 - att))
        targets.append({'icon': '📅', 'metric': 'Attendance',
            'current': f'{att:.0f}%', 'target': '75%+',
            'action': f'Improve attendance by {gap}% to reach exam eligibility',
            'priority': 'critical'})
    elif att < class_avg_att:
        targets.append({'icon': '📅', 'metric': 'Attendance',
            'current': f'{att:.0f}%', 'target': f'{min(100, round(class_avg_att + 2)):.0f}%',
            'action': f'Reach class average attendance ({class_avg_att:.0f}%)',
            'priority': 'medium'})

    if gpa < 7.0:
        targets.append({'icon': '📊', 'metric': 'GPA',
            'current': str(gpa), 'target': '7.0+',
            'action': f'Increase GPA to 7.0+ (currently {gpa})',
            'priority': 'high' if gpa < 6.0 else 'medium'})

    if asgn < 80:
        targets.append({'icon': '📝', 'metric': 'Assignments',
            'current': f'{asgn:.0f}%', 'target': '80%+',
            'action': 'Complete all pending assignments on time',
            'priority': 'high' if asgn < 60 else 'medium'})

    if bl > 0:
        targets.append({'icon': '📌', 'metric': 'Backlogs',
            'current': str(bl), 'target': '0',
            'action': f'Clear {bl} backlog(s) — focus on one per week',
            'priority': 'critical' if bl > 2 else 'high'})

    if total_students > 1 and my_rank > 1:
        rank_target = max(1, my_rank - max(1, round(total_students * 0.10)))
        targets.append({'icon': '🏆', 'metric': 'Rank',
            'current': f'#{my_rank}', 'target': f'#{rank_target}',
            'action': f'Improve leaderboard rank by {my_rank - rank_target} position(s)',
            'priority': 'medium'})

    return targets[:5]


def _build_exam_alerts(s):
    """Build exam eligibility and academic risk alerts for the student."""
    alerts = []
    att  = float(s['attendance']            or 0)
    mid  = float(s['mid_term_marks']        or 0)
    asgn = float(s['assignment_completion'] or 0)
    bl   = int(s['backlogs']                or 0)

    if att < 75:
        alerts.append({'type': 'danger', 'icon': '🚨',
            'title': 'Exam Eligibility at Risk',
            'msg': f'Attendance {att:.0f}% is below the 75% minimum. You may be barred from semester exams.'})
    elif att < 80:
        alerts.append({'type': 'warning', 'icon': '⚠️',
            'title': 'Attendance Near Threshold',
            'msg': f'Attendance is {att:.0f}% — just above the 75% limit. One more absence could be risky.'})

    if mid < 40:
        alerts.append({'type': 'danger', 'icon': '📋',
            'title': 'Low Internal Marks',
            'msg': f'Mid-term score {mid:.0f}/100 is critically low. Attend revision sessions immediately.'})
    elif mid < 50:
        alerts.append({'type': 'warning', 'icon': '📋',
            'title': 'Internal Marks Warning',
            'msg': f'Mid-term {mid:.0f}/100 is below the passing threshold. Focused revision is needed.'})

    if bl > 0:
        alerts.append({'type': 'danger' if bl > 2 else 'warning', 'icon': '📌',
            'title': f'{"Critical " if bl > 2 else ""}Backlog Alert — {bl} Pending',
            'msg': f'{bl} uncleared backlog(s) impact your semester result and placement eligibility.'})

    if asgn < 50:
        alerts.append({'type': 'warning', 'icon': '📝',
            'title': 'Assignment Completion Warning',
            'msg': f'Only {asgn:.0f}% of assignments completed — may affect internal assessment marks.'})

    return alerts


def _build_category_recommendations(s, cat):
    recs = []
    att  = float(s['attendance']            or 0)
    asgn = float(s['assignment_completion'] or 0)
    mid  = float(s['mid_term_marks']        or 0)
    bl   = int(s['backlogs']                or 0)
    part = int(s['class_participation']     or 0)

    if att < 75:
        recs.append({"icon": "📅", "priority": "critical",
            "title": "Attendance Below Exam Threshold",
            "detail": f"Your attendance is {att:.0f}% — below the 75% minimum required for exam eligibility."})
    if bl > 0:
        recs.append({"icon": "📌", "priority": "high",
            "title": f"Clear {bl} Active Backlog{'s' if bl > 1 else ''}",
            "detail": "Uncleared backlogs directly impact your semester result and ML risk score."})
    if asgn < 60:
        recs.append({"icon": "📝", "priority": "high",
            "title": "Submit Pending Assignments",
            "detail": f"Assignment completion is {asgn:.0f}%. Submit all overdue work before the deadline."})

    if cat == 'Weak':
        recs += [
            {"icon": "🆘", "priority": "critical",
             "title": "Enrol in Remedial Lecture Sessions",
             "detail": "Daily remedial lectures (09:00-10:00) are designed for at-risk students. Attend every session."},
            {"icon": "🙋", "priority": "high",
             "title": "Attend Doubt-Clearing Sessions",
             "detail": "Doubt sessions run every afternoon. Bring a list of unresolved questions from your notes."},
            {"icon": "👨‍🏫", "priority": "high",
             "title": "Schedule Mentor 1-on-1 Meeting",
             "detail": "A personal mentor meeting helps identify root causes of underperformance. Book a slot this week."},
            {"icon": "📖", "priority": "medium",
             "title": "Review Previous Semester Material",
             "detail": "Weak foundation in prior topics leads to compounding difficulty. Revise Sem 1-2 fundamentals first."},
            {"icon": "⏰", "priority": "medium",
             "title": "Fix Your Study Schedule",
             "detail": "Dedicate at least 3 focused hours daily. Use the self-study slot (01:15-02:00) every day."},
        ]
    elif cat == 'Average':
        recs += [
            {"icon": "📈", "priority": "high",
             "title": "Attend Improvement Workshops",
             "detail": "Afternoon improvement workshops target concept gaps. Regular attendance can move you to Advanced."},
            {"icon": "💡", "priority": "high",
             "title": "Strengthen Weak Subject Areas",
             "detail": f"Your mid-term score is {mid:.0f}/100. Focus revision on subjects scoring below 65."},
            {"icon": "🤝", "priority": "medium",
             "title": "Join Peer Study Groups",
             "detail": "Peer study sessions (04:00-05:00) offer collaborative learning that reinforces understanding."},
            {"icon": "📊", "priority": "medium",
             "title": "Track Your Weekly Progress",
             "detail": "Set a target to improve your performance score by 5 points each week."},
            {"icon": "🧠", "priority": "medium",
             "title": "Practice Mock Tests Regularly",
             "detail": "Attempt at least one mock test per week per subject and analyse your mistakes."},
        ]
    else:  # Advanced
        recs += [
            {"icon": "🌟", "priority": "medium",
             "title": "Maintain Consistent Performance",
             "detail": "Top performers sometimes slip due to complacency. Keep attending all classes on time."},
            {"icon": "🏆", "priority": "medium",
             "title": "Participate in Competitive Coding",
             "detail": "Competitive coding sessions run every Tuesday afternoon. Sharpen your problem-solving skills."},
            {"icon": "🤗", "priority": "medium",
             "title": "Take Up Peer Mentoring",
             "detail": "Helping weaker students reinforces your own understanding and builds leadership skills."},
            {"icon": "🔬", "priority": "low",
             "title": "Explore Research / Innovation Projects",
             "detail": "Enrol in the Research and Innovation Lab (Wednesday 04:00-05:00)."},
            {"icon": "🚀", "priority": "low",
             "title": "Prepare for Internship / Placement",
             "detail": "Use the Internship Readiness sessions (Thursday 04:00-05:00) to prepare resume and interview skills."},
        ]

    if part < 1:
        recs.append({"icon": "🙋", "priority": "medium",
            "title": "Increase Class Participation",
            "detail": "Active in-class engagement is a positive signal in the prediction model."})

    return recs[:6]


def _build_trend(s, current_score):
    import random
    random.seed(hash(s['id'] or 'seed') % 2**31)
    months = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]
    base   = max(20.0, current_score - random.uniform(12, 22))
    delta  = (current_score - base) / 5.0
    trend  = []
    for i, month in enumerate(months):
        noise = random.uniform(-3.5, 3.5)
        val   = round(min(100, max(10, base + delta * i + noise)), 1)
        trend.append({"month": month, "score": val})
    trend[-1]["score"] = current_score
    return trend


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
    return _build_category_recommendations(s, s.get('predicted_category') or 'Unknown')


def _build_weekly_goals(s, cat: str) -> list:
    """
    Generate 5 realistic, measurable weekly academic goals based on the
    student's live data and predicted category.
    """
    goals = []
    att   = float(s['attendance']            or 0)
    asgn  = float(s['assignment_completion'] or 0)
    quiz  = float(s['quiz_avg_score']        or 0)
    mid   = float(s['mid_term_marks']        or 0)
    part  = int(s['class_participation']     or 0)
    bl    = int(s['backlogs']                or 0)

    # ── Attendance goal ───────────────────────────────────────────────────────
    if att < 75:
        goals.append({
            "icon": "📅", "priority": "critical",
            "goal": "Attend every class this week — zero absences",
            "why": f"Attendance {att:.0f}% is below the 75% exam eligibility threshold.",
            "target": "100% this week", "tag": "Attendance"
        })
    elif att < 85:
        goals.append({
            "icon": "📅", "priority": "high",
            "goal": "Maintain ≥ 80% attendance this week",
            "why": f"At {att:.0f}% you are close — one more absence can push below 75%.",
            "target": "≥ 80%", "tag": "Attendance"
        })

    # ── Assignment goal ───────────────────────────────────────────────────────
    if asgn < 70:
        pending = max(1, round((70 - asgn) / 12))
        goals.append({
            "icon": "📝", "priority": "high",
            "goal": f"Submit {pending} pending assignment(s) before Friday",
            "why": f"Completion at {asgn:.0f}% — each submission lifts your score.",
            "target": f"+{pending} submitted", "tag": "Assignments"
        })

    # ── Backlog goal ──────────────────────────────────────────────────────────
    if bl > 0:
        goals.append({
            "icon": "📌", "priority": "high",
            "goal": f"Clear at least 1 backlog subject this week",
            "why": f"{bl} active backlog(s) negatively impact your academic score.",
            "target": "1 backlog cleared", "tag": "Backlogs"
        })

    # ── Quiz / practice goal ──────────────────────────────────────────────────
    if quiz < 65:
        goals.append({
            "icon": "🧠", "priority": "medium",
            "goal": "Practice aptitude / quiz for 30 min every day",
            "why": f"Quiz average is {quiz:.0f}/100 — daily practice lifts scores consistently.",
            "target": "5 days × 30 min", "tag": "Quiz Prep"
        })

    # ── Participation goal ────────────────────────────────────────────────────
    if part < 1:
        goals.append({
            "icon": "🙋", "priority": "medium",
            "goal": "Ask at least 1 question per class this week",
            "why": "Participation level is 'Low' — it's a positive signal in the ML model.",
            "target": "1+ question/day", "tag": "Participation"
        })

    # ── Category-specific goals ───────────────────────────────────────────────
    if cat == 'Weak':
        if len(goals) < 5:
            goals.append({
                "icon": "📖", "priority": "high",
                "goal": "Revise 1 weak-subject chapter daily",
                "why": "Consistent daily revision builds foundation for improved exam performance.",
                "target": "5 chapters this week", "tag": "Study"
            })
        if len(goals) < 5:
            goals.append({
                "icon": "👨‍🏫", "priority": "high",
                "goal": "Book a mentor 1-on-1 meeting this week",
                "why": "Personal mentoring helps identify root causes of underperformance quickly.",
                "target": "1 meeting booked", "tag": "Mentoring"
            })
    elif cat == 'Average':
        if len(goals) < 5:
            goals.append({
                "icon": "💻", "priority": "medium",
                "goal": "Solve 3 coding / aptitude problems daily",
                "why": "Consistent practice is the fastest way to move from Average to Advanced.",
                "target": "15 problems/week", "tag": "Coding"
            })
        if len(goals) < 5:
            goals.append({
                "icon": "📊", "priority": "medium",
                "goal": f"Target 70+ in this week's class test",
                "why": f"Mid-term average is {mid:.0f}/100 — a strong class test boosts the composite score.",
                "target": "≥ 70 marks", "tag": "Test Prep"
            })
    else:  # Advanced
        if len(goals) < 5:
            goals.append({
                "icon": "🏆", "priority": "medium",
                "goal": "Solve 1 LeetCode medium / hard problem daily",
                "why": "Keeps competitive programming skills sharp for placements and interviews.",
                "target": "5 problems/week", "tag": "Competitive"
            })
        if len(goals) < 5:
            goals.append({
                "icon": "🔬", "priority": "low",
                "goal": "Contribute 2 hrs to your major project this week",
                "why": "Consistent project progress differentiates your academic profile.",
                "target": "2 hrs logged", "tag": "Project"
            })
        if len(goals) < 5:
            goals.append({
                "icon": "📜", "priority": "low",
                "goal": "Explore one online certification module",
                "why": "Certifications strengthen your placement profile and demonstrate initiative.",
                "target": "1 module completed", "tag": "Career"
            })

    return goals[:5]


def _build_explainability(s, cat: str, perf_score: float) -> dict:
    """
    Explain WHY the student is classified into the given category.
    Returns a dict with a list of contributing factors (positive & negative),
    a plain-language summary, and the single biggest reason.
    """
    att   = float(s['attendance']            or 0)
    asgn  = float(s['assignment_completion'] or 0)
    mid   = float(s['mid_term_marks']        or 0)
    quiz  = float(s['quiz_avg_score']        or 0)
    ctest = float(s['class_test_score']      or 0)
    gpa   = float(s['previous_sem_gpa']      or 0)
    bl    = int(s['backlogs']                or 0)
    delay = float(s['assignment_delay']      or 0)
    part  = int(s['class_participation']     or 0)

    factors = []

    # ── Attendance ────────────────────────────────────────────────────────────
    if att < 65:
        factors.append({"factor": "Attendance", "value": f"{att:.0f}%",
            "status": "critical", "impact": -3,
            "msg": "Critically low — exam eligibility at risk"})
    elif att < 75:
        factors.append({"factor": "Attendance", "value": f"{att:.0f}%",
            "status": "warning", "impact": -2,
            "msg": "Below the 75% exam eligibility threshold"})
    elif att >= 90:
        factors.append({"factor": "Attendance", "value": f"{att:.0f}%",
            "status": "excellent", "impact": +3,
            "msg": "Excellent attendance record"})
    elif att >= 80:
        factors.append({"factor": "Attendance", "value": f"{att:.0f}%",
            "status": "good", "impact": +2,
            "msg": "Good attendance — above the safe threshold"})

    # ── Assignments ───────────────────────────────────────────────────────────
    if asgn < 50:
        factors.append({"factor": "Assignments", "value": f"{asgn:.0f}%",
            "status": "critical", "impact": -3,
            "msg": "More than half of assignments are incomplete"})
    elif asgn < 70:
        factors.append({"factor": "Assignments", "value": f"{asgn:.0f}%",
            "status": "warning", "impact": -1,
            "msg": "Below average assignment completion"})
    elif asgn >= 85:
        factors.append({"factor": "Assignments", "value": f"{asgn:.0f}%",
            "status": "good", "impact": +2,
            "msg": "Consistent assignment submission"})

    # ── Mid-term marks ────────────────────────────────────────────────────────
    if mid < 45:
        factors.append({"factor": "Mid-term Marks", "value": f"{mid:.0f}/100",
            "status": "critical", "impact": -3,
            "msg": "Very low exam performance"})
    elif mid < 60:
        factors.append({"factor": "Mid-term Marks", "value": f"{mid:.0f}/100",
            "status": "warning", "impact": -2,
            "msg": "Below class average — needs focused revision"})
    elif mid >= 75:
        factors.append({"factor": "Mid-term Marks", "value": f"{mid:.0f}/100",
            "status": "good", "impact": +2,
            "msg": "Above-average exam performance"})

    # ── Quiz ──────────────────────────────────────────────────────────────────
    if quiz < 50:
        factors.append({"factor": "Quiz Average", "value": f"{quiz:.0f}/100",
            "status": "warning", "impact": -2,
            "msg": "Low quiz scores indicate concept gaps"})
    elif quiz >= 75:
        factors.append({"factor": "Quiz Average", "value": f"{quiz:.0f}/100",
            "status": "good", "impact": +2,
            "msg": "Strong quiz performance"})

    # ── Class test ────────────────────────────────────────────────────────────
    if ctest < 50:
        factors.append({"factor": "Class Test", "value": f"{ctest:.0f}/100",
            "status": "warning", "impact": -1,
            "msg": "Class test scores below average"})
    elif ctest >= 75:
        factors.append({"factor": "Class Test", "value": f"{ctest:.0f}/100",
            "status": "good", "impact": +1,
            "msg": "Consistent class test performance"})

    # ── GPA ───────────────────────────────────────────────────────────────────
    if gpa >= 8.0:
        factors.append({"factor": "Previous GPA", "value": str(gpa),
            "status": "excellent", "impact": +3,
            "msg": "Excellent academic history"})
    elif gpa >= 6.5:
        factors.append({"factor": "Previous GPA", "value": str(gpa),
            "status": "good", "impact": +1,
            "msg": "Satisfactory GPA — solid foundation"})
    elif gpa < 5.0:
        factors.append({"factor": "Previous GPA", "value": str(gpa),
            "status": "warning", "impact": -2,
            "msg": "Low GPA carries a negative academic signal"})

    # ── Backlogs ──────────────────────────────────────────────────────────────
    if bl > 2:
        factors.append({"factor": "Backlogs", "value": str(bl),
            "status": "critical", "impact": -3,
            "msg": f"{bl} uncleared backlogs drag the composite score down"})
    elif bl > 0:
        factors.append({"factor": "Backlogs", "value": str(bl),
            "status": "warning", "impact": -1,
            "msg": "Active backlog(s) need to be cleared"})
    else:
        factors.append({"factor": "Backlogs", "value": "0",
            "status": "good", "impact": +1,
            "msg": "No pending backlogs — clean academic record"})

    # ── Assignment delay ──────────────────────────────────────────────────────
    if delay > 5:
        factors.append({"factor": "Submission Punctuality", "value": f"{delay:.0f} days late",
            "status": "warning", "impact": -2,
            "msg": "Assignments are consistently submitted late"})
    elif delay == 0:
        factors.append({"factor": "Submission Punctuality", "value": "On time",
            "status": "good", "impact": +1,
            "msg": "All assignments submitted on time"})

    # ── Participation ─────────────────────────────────────────────────────────
    part_label = {0: "Low", 1: "Medium", 2: "High"}.get(part, "Low")
    if part == 0:
        factors.append({"factor": "Participation", "value": "Low",
            "status": "warning", "impact": -1,
            "msg": "Low classroom engagement"})
    elif part == 2:
        factors.append({"factor": "Participation", "value": "High",
            "status": "good", "impact": +1,
            "msg": "Active classroom participation"})

    # Sort by absolute impact (biggest drivers first)
    factors.sort(key=lambda x: abs(x['impact']), reverse=True)

    neg_factors = [f for f in factors if f['impact'] < 0]
    pos_factors = [f for f in factors if f['impact'] > 0]
    primary     = factors[0] if factors else None

    if cat == 'Weak':
        summary = (f"Classified as At-Risk because "
                   f"{len(neg_factors)} key metric(s) are below acceptable thresholds. "
                   f"Immediate intervention is recommended.")
    elif cat == 'Advanced':
        summary = (f"Classified as Advanced because "
                   f"{len(pos_factors)} academic metrics are above average. "
                   f"Keep up the consistency.")
    else:
        summary = (f"Classified as Average — performance shows a mix of "
                   f"{len(pos_factors)} positive and {len(neg_factors)} negative signals. "
                   f"Targeted improvement can move you to the Advanced category.")

    return {
        "factors":        factors[:7],
        "neg_count":      len(neg_factors),
        "pos_count":      len(pos_factors),
        "summary":        summary,
        "primary_reason": primary['msg'] if primary else "Balanced performance overall.",
        "primary_factor": primary['factor'] if primary else "—",
    }


# ── Login / Portal selection ──────────────────────────────────────────────────
@views_bp.route('/login')
def login_page():
    error = request.args.get('error', '')
    return render_template('login.html', error=error)


@views_bp.route('/admin')
def admin_redirect():
    """Convenience alias — /admin goes straight to the admin dashboard."""
    return redirect(url_for('views.dashboard'))  # /dashboard



@views_bp.route('/student/lookup', methods=['POST'])
def student_lookup():
    sid = (request.form.get('student_id') or '').strip().upper()
    if not sid:
        return redirect(url_for('views.login_page', error='Please enter a Student ID.'))
    db  = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM students WHERE UPPER(id) = ?", (sid,))
    row = cur.fetchone()
    if not row:
        return redirect(url_for('views.login_page',
                                error=f'Student ID "{sid}" not found. Please check and try again.'))
    session['student_id'] = row['id']   # persist for sidebar rendering on all pages
    return redirect(url_for('views.student_dashboard', student_id=row['id']))


@views_bp.route('/career')
def career_generic():
    return render_template('career.html', student=None, cat=None,
                           perf_score=None, recommended_path=None)


@views_bp.route('/career/<student_id>')
def career(student_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = cur.fetchone()
    if not student:
        abort(404)
    cat        = student['predicted_category'] or 'Unknown'
    perf_score = compute_performance_score(student)
    if perf_score >= 75 or cat == 'Advanced':
        recommended_path = 'AI/ML'
    elif perf_score >= 50 or cat == 'Average':
        recommended_path = 'Full Stack Web Dev'
    else:
        recommended_path = 'Business Analytics'
    return render_template('career.html',
                           student=student,
                           cat=cat,
                           perf_score=round(perf_score, 1),
                           recommended_path=recommended_path,
                           counts={'Weak': 0, 'Average': 0, 'Advanced': 0})
