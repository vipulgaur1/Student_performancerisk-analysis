# Student Early Performance Prediction System (SEPPS)

An end-to-end machine learning web application that classifies students into academic risk categories, enabling faculty and administrators to identify struggling students early and plan timely interventions.

![Python](https://img.shields.io/badge/Python-3.x-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-Web%20App-black?style=flat-square&logo=flask)
![Scikit-learn](https://img.shields.io/badge/Scikit--learn-ML-orange?style=flat-square&logo=scikit-learn)
![SQLite](https://img.shields.io/badge/SQLite-Database-lightgrey?style=flat-square&logo=sqlite)

---

## Overview

Academic institutions collect large amounts of student data every semester — attendance records, assessment scores, assignment logs, and behavioural indicators — but rarely use it proactively. SEPPS bridges this gap by applying supervised machine learning to classify each student into one of three risk levels:

| Risk Level | Label | Meaning |
|---|---|---|
| High | Weak / At Risk | Immediate faculty attention required |
| Medium | Average / Monitor | Needs periodic monitoring and check-ins |
| Low | Advanced / Safe | On track, performing well |

Predictions are served through an interactive Flask web dashboard that supports both individual student assessment and bulk CSV upload for entire cohorts.

---

## Features

- ML-powered three-tier student risk classification
- CSV batch prediction — upload an entire class and receive predictions instantly
- Individual student scoring via manual form entry
- Interactive dashboard with risk distribution charts, confusion matrix, and model comparison
- SQLite-backed prediction history for reviewing past results
- Decision Tree visualisation to inspect model decision rules
- Actionable recommendations output per risk category

---

## Machine Learning Pipeline

```
Raw CSV Data
    |
    v
Data Cleaning & Missing Value Handling
    |
    v
Feature Engineering & Categorical Encoding
    |
    v
Rule-based Risk Label Generation
    |
    v
Model Training (80/20 Train-Test Split)
    |
    v
Model Evaluation (Accuracy, F1, Confusion Matrix)
    |
    v
Model Serialization (.pkl)
    |
    v
Flask Prediction API  -->  Dashboard Visualisation
```

---

## Dataset

- **Records:** 400 student entries  
- **Features:** 12 academic and behavioural attributes

| Feature | Description |
|---|---|
| `mid_term_marks` | Marks obtained in mid-term examination |
| `attendance` | Attendance percentage |
| `backlogs` | Number of pending backlogs |
| `behaviour` | Behavioural performance indicator |
| `assignment_delay` | Delay in assignment submission |
| `class_test_score` | Average class test marks |
| `quiz_avg_score` | Average quiz marks |
| `assignment_completion` | Assignment completion percentage |
| `previous_sem_gpa` | GPA from previous semester |
| `class_participation` | Classroom participation level |
| `doubt_asking` | Frequency of asking doubts in class |
| `attention_level` | Attention level during lectures |

---

## Model Performance

Three classifiers were trained and evaluated on the same dataset:

| Model | Accuracy | F1 Score | Notes |
|---|---|---|---|
| Random Forest | 87% | 0.85 | Deployed model |
| Logistic Regression | 85% | 0.83 | Baseline classifier |

The Random Forest classifier was selected for deployment based on its higher accuracy and consistent performance across all three risk classes.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| Machine Learning | Scikit-learn, Pandas, NumPy |
| Visualisation | Matplotlib, Seaborn |
| Database | SQLite |
| Frontend | HTML, CSS, JavaScript |

---

## Project Structure

```
student_performance/
|
|-- app.py                  # Flask application entry point
|-- load_data.py            # Dataset loading and preprocessing
|-- requirements.txt        # Python dependencies
|-- students_400.csv        # Student dataset
|
|-- ml_pipeline/            # Model training and evaluation scripts
|-- models/                 # Serialized trained models (.pkl)
|-- routes/                 # Flask route definitions
|-- services/               # Prediction and data service logic
|-- database/               # SQLite database files
|-- templates/              # HTML templates (Jinja2)
|-- static/                 # CSS, JS, and static assets
|
+-- docs/
    +-- ML_Project_Documentation.docx
```

---

## Getting Started

### Prerequisites

- Python 3.8 or higher
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/vipulgaur1/Student_performancerisk-analysis.git
cd Student_performancerisk-analysis

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

The dashboard will be available at `http://localhost:5000`.

### CSV Upload Format

The batch prediction module expects a CSV with the following columns:

```
id, name, branch, semester, year, attendance, mid_term_marks,
class_test_score, quiz_avg_score, assignment_completion,
assignment_delay, previous_sem_gpa, backlogs,
class_participation, doubt_asking, attention_level, behaviour
```

---


## Future Scope

- Deep learning integration for larger datasets
- Real-time monitoring via LMS or ERP integration
- Automated email alerts for high-risk students
- Role-based authentication for faculty and admin
- Cloud deployment (Render / Railway / AWS)
- Mobile-friendly responsive interface

---

## Author

**Vipul Gaur**  
MCA — Manipal University Jaipur  
[LinkedIn](https://linkedin.com/in/vipul-gaur-analyst) · [GitHub](https://github.com/vipulgaur1)
