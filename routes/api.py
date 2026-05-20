from flask import Blueprint, request, jsonify
from database.db import get_db
from services.prediction_service import predict_category, predict_batch
import pandas as pd
import io

api_bp = Blueprint('api', __name__)


@api_bp.route('/students', methods=['POST'])
def add_student():
    data = request.json
    try:
        db = get_db()
        cursor = db.cursor()

        student_id = data.get('student_id')

        pred, conf, action = predict_category(data)

        sql = """
            INSERT INTO students (
                id, name, branch, semester, year,
                attendance, mid_term_marks, class_test_score,
                quiz_avg_score, assignment_completion, assignment_delay,
                previous_sem_gpa, backlogs,
                class_participation, doubt_asking,
                attention_level, behaviour,
                predicted_category, confidence, recommended_action
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                predicted_category=EXCLUDED.predicted_category,
                confidence=EXCLUDED.confidence,
                recommended_action=EXCLUDED.recommended_action
        """
        vals = (
            student_id,
            data.get('name'),
            data.get('branch'),
            data.get('semester'),
            data.get('year'),
            data.get('attendance', 0),
            data.get('mid_term_marks', 0),
            data.get('class_test_score', 0),
            data.get('quiz_avg_score', 0),
            data.get('assignment_completion', 0),
            data.get('assignment_delay', 0),
            data.get('previous_sem_gpa', 0),
            data.get('backlogs', 0),
            data.get('class_participation', 0),
            data.get('doubt_asking', 0),
            data.get('attention_level', 0),
            data.get('behaviour', 0),
            pred, conf, action
        )
        cursor.execute(sql, vals)
        db.commit()
        return jsonify({
            'message': 'Student added successfully',
            'prediction': pred,
            'confidence': conf,
            'recommended_action': action
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 400


@api_bp.route('/predict_all', methods=['POST'])
def predict_all():
    """
    Re-run the model on every student already in the database.

    Optimised: one predict_batch() call instead of N predict_category() calls,
    and one executemany() instead of N individual UPDATE statements.
    """
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT * FROM students")
        students = cursor.fetchall()

        if not students:
            return jsonify({'message': 'No students found.'}), 200

        student_dicts = [dict(s) for s in students]

        # Single batch model call instead of one predict_category() per student
        batch_results = predict_batch(student_dicts)

        # Build all update tuples, then write in one executemany call
        update_rows = [
            (pred, conf, action, student_dicts[i]['id'])
            for i, (pred, conf, action) in enumerate(batch_results)
        ]

        cursor.executemany(
            """UPDATE students
               SET predicted_category=?, confidence=?, recommended_action=?
               WHERE id=?""",
            update_rows,
        )
        db.commit()
        return jsonify({'message': f'Updated predictions for {len(update_rows)} students.'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/students/<student_id>', methods=['DELETE'])
def delete_student(student_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        db.commit()
        return jsonify({'message': 'Student deleted successfully.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/students', methods=['GET'])
def get_students():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM students ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/upload_csv', methods=['POST'])
def upload_csv():
    """
    Parse a CSV, run batch ML inference, and bulk-insert into SQLite.

    Key optimisations vs. the old row-by-row approach:
      1. predict_batch()   -- one model call for all N rows instead of N calls
      2. executemany()     -- one DB round-trip instead of N cursor.execute()s
      3. Column flags      -- optional-column checks done once, outside any loop
      4. Vectorised access -- feature values extracted as Python lists before
                             the insert loop (avoids repeated pandas Series ops)
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Invalid file type, must be CSV'}), 400

    try:
        stream = io.StringIO(file.stream.read().decode("UTF-8"))
        df = pd.read_csv(stream)
        df.columns = df.columns.str.strip()

        required_cols = [
            'attendance', 'mid_term_marks', 'class_test_score',
            'quiz_avg_score', 'assignment_completion', 'assignment_delay',
            'previous_sem_gpa', 'backlogs', 'class_participation',
            'doubt_asking', 'attention_level', 'behaviour',
        ]

        for col in required_cols:
            if col not in df.columns:
                return jsonify({'error': f'Missing column: {col}'}), 400

        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Reset index so positional access works correctly after row drops
        df = df.dropna(subset=required_cols).reset_index(drop=True)

        if df.empty:
            return jsonify({'error': 'No valid rows after cleaning'}), 400

        n = len(df)

        # -- BATCH INFERENCE -------------------------------------------------
        # Build list-of-dicts from only the required feature columns, then
        # predict all N rows in a single model call.  The old code called
        # predict_category() once per row -- for 400 rows that was ~485 ms;
        # predict_batch() does the same work in ~5 ms.
        raw_data_list = df[required_cols].to_dict('records')
        batch_results = predict_batch(raw_data_list)

        # -- OPTIONAL COLUMN FLAGS (checked once, not inside any loop) --------
        has_id       = 'id'       in df.columns
        has_name     = 'name'     in df.columns
        has_branch   = 'branch'   in df.columns
        has_semester = 'semester' in df.columns
        has_year     = 'year'     in df.columns

        # -- VECTORISED METADATA EXTRACTION -----------------------------------
        # Convert each column to a plain Python list once; indexing a list is
        # ~5x faster than repeated pandas Series __getitem__ inside a loop.
        student_ids = df['id'].astype(str).tolist()   if has_id     else [f"STU{i}"      for i in range(n)]
        names       = df['name'].astype(str).tolist() if has_name   else [f"Student {i}" for i in range(n)]
        branches    = df['branch'].astype(str).tolist() if has_branch else ['CSE'] * n

        if has_semester:
            semesters = [int(v) if pd.notna(v) else None for v in df['semester']]
        else:
            semesters = [None] * n

        if has_year:
            years = [int(v) if pd.notna(v) else None for v in df['year']]
        else:
            years = [None] * n

        # Pre-extract all feature columns as Python lists (one pass each)
        feat = {col: df[col].tolist() for col in required_cols}

        # -- BUILD ALL INSERT TUPLES IN ONE LIST COMPREHENSION ----------------
        rows_to_insert = [
            (
                student_ids[i], names[i], branches[i], semesters[i], years[i],
                feat['attendance'][i],            feat['mid_term_marks'][i],
                feat['class_test_score'][i],      feat['quiz_avg_score'][i],
                feat['assignment_completion'][i], feat['assignment_delay'][i],
                feat['previous_sem_gpa'][i],      feat['backlogs'][i],
                feat['class_participation'][i],   feat['doubt_asking'][i],
                feat['attention_level'][i],       feat['behaviour'][i],
                batch_results[i][0],  # prediction
                batch_results[i][1],  # confidence
                batch_results[i][2],  # recommended_action
            )
            for i in range(n)
        ]

        # -- SINGLE BULK INSERT -----------------------------------------------
        # executemany() batches all rows into one SQLite transaction step,
        # replacing 400 individual cursor.execute() calls.
        db = get_db()
        cursor = db.cursor()
        cursor.executemany(
            """
            INSERT INTO students (
                id, name, branch, semester, year,
                attendance, mid_term_marks, class_test_score,
                quiz_avg_score, assignment_completion, assignment_delay,
                previous_sem_gpa, backlogs,
                class_participation, doubt_asking,
                attention_level, behaviour,
                predicted_category, confidence, recommended_action
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                predicted_category=EXCLUDED.predicted_category,
                confidence=EXCLUDED.confidence,
                recommended_action=EXCLUDED.recommended_action
            """,
            rows_to_insert,
        )
        db.commit()
        return jsonify({'message': f'Successfully uploaded and predicted {n} students'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- Student Dashboard API --------------------------------------------------
@api_bp.route('/students/<student_id>/dashboard', methods=['GET'])
def get_student_dashboard(student_id):
    from datetime import datetime

    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM students WHERE id = ?", (student_id,))
        s = cur.fetchone()
        if not s:
            return jsonify({'error': f'Student {student_id} not found'}), 404

        s = dict(s)
        cat    = s['predicted_category'] or 'Unknown'
        status = "At Risk" if cat == 'Weak' else ("Safe" if cat == 'Advanced' else "Monitor")

        overall = round(
            float(s['attendance'] or 0)           * 0.30 +
            float(s['assignment_completion'] or 0) * 0.25 +
            float(s['mid_term_marks'] or 0)        * 0.25 +
            float(s['quiz_avg_score'] or 0)        * 0.20, 1
        )

        prev_gpa  = float(s['previous_sem_gpa'] or 0)
        pred_cgpa = round(max(0.0, min(10.0, prev_gpa + (overall - 60) / 100 * 0.5)), 2)

        dropout = round(max(0.0, min(99.0,
            (75 - float(s['attendance'] or 0))            * 0.5 +
            (70 - float(s['assignment_completion'] or 0)) * 0.3 +
            (60 - float(s['mid_term_marks'] or 0))        * 0.2
        )), 1)

        participation_pct = {0: 20, 1: 55, 2: 90}.get(int(s['class_participation'] or 0), 20)
        punctuality       = max(0, 100 - int(s['assignment_delay'] or 0) * 10)

        return jsonify({
            "name":             s['name'],
            "id":               s['id'],
            "branch":           s['branch'] or "B.Tech",
            "semester":         f"Semester {s['semester']}" if s['semester'] else "-",
            "dropout_prob":     dropout,
            "predicted_cgpa":   pred_cgpa,
            "overall_score":    overall,
            "status":           status,
            "model_conf":       round(float(s['confidence'] or 0), 1),
            "attendance":       round(float(s['attendance'] or 0), 1),
            "assignment_score": round(float(s['assignment_completion'] or 0), 1),
            "marks":            round(float(s['mid_term_marks'] or 0), 1),
            "participation":    participation_pct,
            "backlogs":         int(s['backlogs'] or 0),
            "punctuality":      punctuality,
            "rank":             "-",
            "class_size":       "-",
            "shap_values":      [],
            "recommendations":  [],
            "last_updated":     datetime.now().strftime("%d %b %Y, %I:%M %p"),
            "radar": [
                {"subject": "Attendance",    "A": round(float(s['attendance'] or 0), 1)},
                {"subject": "Assignments",   "A": round(float(s['assignment_completion'] or 0), 1)},
                {"subject": "Mid-term",      "A": round(float(s['mid_term_marks'] or 0), 1)},
                {"subject": "Participation", "A": participation_pct},
                {"subject": "CGPA Trend",    "A": round(min(pred_cgpa / 10 * 100, 100), 1)},
                {"subject": "Punctuality",   "A": punctuality},
            ],
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Intervention Tracker ──────────────────────────────────────────────────────
@api_bp.route('/interventions/<student_id>', methods=['POST'])
def save_intervention(student_id):
    """Save or update the intervention flags for a student."""
    try:
        data = request.json or {}
        db   = get_db()
        cur  = db.cursor()
        cur.execute("""
            INSERT INTO interventions
                (student_id, mentoring_done, remedial_assigned, parent_contacted,
                 counselling_suggested, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(student_id) DO UPDATE SET
                mentoring_done        = excluded.mentoring_done,
                remedial_assigned     = excluded.remedial_assigned,
                parent_contacted      = excluded.parent_contacted,
                counselling_suggested = excluded.counselling_suggested,
                notes                 = excluded.notes,
                updated_at            = CURRENT_TIMESTAMP
        """, (
            student_id,
            1 if data.get('mentoring_done')        else 0,
            1 if data.get('remedial_assigned')     else 0,
            1 if data.get('parent_contacted')      else 0,
            1 if data.get('counselling_suggested') else 0,
            data.get('notes', ''),
        ))
        db.commit()
        return jsonify({'message': 'Intervention saved.'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
