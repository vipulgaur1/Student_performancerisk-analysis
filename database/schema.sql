-- database/schema.sql
-- Pure SQLite schema — no MySQL-specific statements.
-- Matches the 12-feature canonical model exactly.

DROP TABLE IF EXISTS students;

CREATE TABLE students (
    id                    VARCHAR(50)  PRIMARY KEY,
    name                  VARCHAR(100),
    branch                VARCHAR(50),
    semester              INT,
    year                  INT,

    -- 12 canonical ML features
    attendance            FLOAT,
    mid_term_marks        FLOAT,
    class_test_score      FLOAT,
    quiz_avg_score        FLOAT,
    assignment_completion FLOAT,
    assignment_delay      FLOAT,
    previous_sem_gpa      FLOAT,
    backlogs              INT,
    class_participation   INT,       -- 0 = low, 1 = medium, 2 = high
    doubt_asking          INT,       -- 0 = low, 1 = medium, 2 = high
    attention_level       INT,       -- 0 = low, 1 = medium, 2 = high
    behaviour             INT,       -- 0 = low, 1 = medium, 2 = high

    -- Prediction outputs
    predicted_category    VARCHAR(50),
    confidence            FLOAT,
    recommended_action    TEXT,

    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);