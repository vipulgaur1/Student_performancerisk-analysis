from flask import Blueprint, request, jsonify
from database.db import get_db
from services.prediction_service import predict_category
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
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT * FROM students")
        students = cursor.fetchall()

        updated_count = 0
        for s in students:
            s_id = s['id']
            pred, conf, action = predict_category(dict(s))
            cursor.execute(
                """UPDATE students
                   SET predicted_category=?, confidence=?, recommended_action=?
                   WHERE id=?""",
                (pred, conf, action, s_id)
            )
            updated_count += 1

        db.commit()
        return jsonify({'message': f'Updated predictions for {updated_count} students.'})

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
            'doubt_asking', 'attention_level', 'behaviour'
        ]

        for col in required_cols:
            if col not in df.columns:
                return jsonify({'error': f'Missing column: {col}'}), 400

        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=required_cols)

        if df.empty:
            return jsonify({'error': 'No valid rows after cleaning'}), 400

        db = get_db()
        cursor = db.cursor()
        count = 0

        for index, row in df.iterrows():
            student_data = {col: row[col] for col in required_cols}
            pred, conf, action = predict_category(student_data)

            student_id = str(row.get('id', f"STU{index}"))
            name       = str(row.get('name',   f"Student {index}"))
            branch     = str(row.get('branch', 'CSE'))
            semester   = int(row['semester']) if 'semester' in df.columns and pd.notna(row['semester']) else None
            year       = int(row['year'])     if 'year'     in df.columns and pd.notna(row['year'])     else None

            cursor.execute("""
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
            """, (
                student_id, name, branch, semester, year,
                row['attendance'],            row['mid_term_marks'],
                row['class_test_score'],      row['quiz_avg_score'],
                row['assignment_completion'], row['assignment_delay'],
                row['previous_sem_gpa'],      row['backlogs'],
                row['class_participation'],   row['doubt_asking'],
                row['attention_level'],       row['behaviour'],
                pred, conf, action
            ))
            count += 1

        db.commit()
        return jsonify({'message': f'Successfully uploaded and predicted {count} students'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── NEW: Student Dashboard API ───────────────────────────────────────────────
@api_bp.route('/students/<student_id>/dashboard', methods=['GET'])
def get_student_dashboard(student_id):
    from datetime import datetime
    # from routes.views import _build_shap_values, _build_recommendations

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
            "semester":         f"Semester {s['semester']}" if s['semester'] else "—",
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
            "rank":             "—",
            "class_size":       "—",
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