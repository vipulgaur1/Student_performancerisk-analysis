import sqlite3
import pandas as pd
import os

from database.db import DATABASE, init_db

def load_data():
    csv_path = 'dataset/student_data.csv'
    
    # ensure db exists
    conn = sqlite3.connect('database/database.db')
    cursor = conn.cursor()
    
    with open('database/schema.sql', 'r') as f:
        sql = f.read()
        sql = sql.replace('CREATE DATABASE IF NOT EXISTS student_performance;', '')
        sql = sql.replace('USE student_performance;', '')
        cursor.executescript(sql)
    conn.commit()
    
    df = pd.read_csv(csv_path)
    
    for _, row in df.iterrows():
        sid = row['student_id']
        cursor.execute("SELECT id FROM students WHERE id=?", (sid,))
        if cursor.fetchone():
            continue
            
        sql = """
            INSERT INTO students (
                id, name, branch, semester, year, attendance, class_test_score, 
                assignment_score, study_hours, doubt_count, behavior_score, 
                backlogs, predicted_category, confidence, recommended_action
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
        """
        vals = (
            sid, f"Student {sid[-4:]}", row['branch'], row['semester'], int(row['year']),
            float(row['attendance']), float(row['class_test_score']), float(row['assignment_score']),
            float(row['study_hours']), int(row['doubt_count']), int(row['behavior_score']), int(row['backlogs'])
        )
        cursor.execute(sql, vals)
                           
    conn.commit()
    print(f"Loaded {len(df)} records into the database.")
    conn.close()

if __name__ == '__main__':
    load_data()
