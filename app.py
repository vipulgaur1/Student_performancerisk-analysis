from flask import Flask
from database.db import init_db, close_connection
from routes.api import api_bp
from routes.views import views_bp
from flask_cors import CORS
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecretkey')

CORS(app)  # React frontend ko allow karta hai

app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(views_bp)

@app.route('/test_db')
def test_db():
    from database.db import get_db
    try:
        db = get_db()
        db.cursor().execute("SELECT 1")
        return "Database connection successful.", 200
    except Exception as e:
        return f"Database connection failed: {str(e)}", 500

@app.teardown_appcontext
def teardown_db(exception):
    close_connection(exception)

if __name__ == '__main__':
    with app.app_context():
        try:
            init_db()
            print("✅ Database initialised.")
        except Exception as e:
            print(f"❌ Could not initialise DB on startup: {e}")
    app.run(debug=True, port=5000)