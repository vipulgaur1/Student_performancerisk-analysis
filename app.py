from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        attendance = float(request.form["attendance"])
        marks = float(request.form["marks"])
        assignment = float(request.form["assignment"])

        score = attendance * 0.3 + marks * 0.5 + assignment * 0.2

        if score >= 75:
            status = "Excellent"
            risk = "Low Risk"
            recommendation = "Maintain consistency and continue regular practice."
        elif score >= 50:
            status = "Average"
            risk = "Medium Risk"
            recommendation = "Focus on improving attendance and assignment performance."
        else:
            status = "At Risk"
            risk = "High Risk"
            recommendation = "Immediate academic improvement required. Focus on weak areas."

        return render_template(
            "dashboard.html",
            score=round(score, 2),
            status=status,
            risk=risk,
            attendance=attendance,
            marks=marks,
            assignment=assignment,
            recommendation=recommendation
)

    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True)
