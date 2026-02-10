# Student Performance Prediction and Academic Risk Analysis System

## Overview
This project is a Flask-based academic analytics system designed to analyze student academic data and identify students who are at academic risk. The system provides a simple, explainable dashboard that helps students and faculty understand performance trends instead of relying on black-box predictions.

The focus of this project is **system design, data analysis, and visualization**, not just machine learning accuracy.

---

## Problem Statement
In academic institutions, students often lack clarity about their academic standing until it is too late. Faculty members managing multiple students also find it difficult to continuously monitor individual performance.

This system aims to:
- Analyze academic performance indicators
- Identify students at risk
- Provide clear, visual feedback for better decision-making

---

## Proposed Solution
The system collects structured academic inputs (such as marks, attendance, and performance indicators), processes them on the backend, and presents the results through a web-based dashboard.

Key objectives:
- Early identification of academic risk
- Simple and interpretable performance insights
- Student self-assessment support
- Faculty-level monitoring assistance

---

## System Architecture
1. **Frontend (HTML Templates)**  
   - User input form
   - Dashboard for performance insights
   - Result page showing academic risk status

2. **Backend (Flask - Python)**  
   - Handles routing and data processing
   - Applies logic for academic risk analysis
   - Sends processed results to frontend templates

3. **Data Processing Layer**
   - Rule-based / statistical logic for performance evaluation
   - Easily extendable to ML models in future

---

## Technologies Used
- Python
- Flask
- HTML5
- CSS (basic styling)
- Jinja2 Templates
- Git & GitHub

---

## Project Structure
