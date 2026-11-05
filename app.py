import os
import re
import requests
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'postgresql://postgres:1234@localhost:5432/nasa_db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

APOD_URL = 'https://science.nasa.gov/wp-json/wp/v2/apod-basic'


class Apod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    explanation = db.Column(db.Text)
    url = db.Column(db.Text)
    hdurl = db.Column(db.Text)
    media_type = db.Column(db.String(20))
    copyright = db.Column(db.String(300))
    fetched_at = db.Column(db.DateTime, server_default=db.func.now())


def fetch_and_save_apod():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        resp = requests.get(APOD_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        items = resp.json()
    except requests.RequestException as e:
        print(f"API request failed: {e}")
        return None
    except ValueError:
        print("JSON parse failed")
        return None

    if not isinstance(items, list):
        print("Unexpected response format")
        return None

    saved = 0
    for item in items:
        d = item.get('date')
        title = item.get('title', 'No Title')
        image_url = item.get('hdurl') or item.get('url')
        if not d or not image_url:
            continue
        if title == 'NASA Science':
            continue
        if not Apod.query.filter_by(date=d).first():
            raw_explanation = item.get('explanation', '')
            clean_explanation = re.sub(r'<[^>]+>', '', raw_explanation).strip()
            raw_credit = item.get('copyright') or item.get('credit') or 'NASA'
            clean_credit = re.sub(r'<[^>]+>', '', raw_credit).strip()
            db.session.add(Apod(
                date=d,
                title=title,
                explanation=clean_explanation,
                url=image_url,
                hdurl=image_url,
                media_type=item.get('media_type', 'image'),
                copyright=clean_credit
            ))
            saved += 1

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"DB commit failed: {e}")
        return None

    print(f"Saved {saved} new APOD record(s)")
    return True


@app.route('/')
def index():
    if Apod.query.count() == 0:
        fetch_and_save_apod()
    pictures = Apod.query.order_by(Apod.date.desc()).all()
    return render_template('index.html', pictures=pictures)


@app.route('/fetch', methods=['POST'])
def fetch_latest():
    fetch_and_save_apod()
    return redirect(url_for('index'))


@app.route('/database')
def database_view():
    rows = Apod.query.order_by(Apod.date.desc()).all()
    return render_template('database.html', rows=rows)


with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True, port=5000)
