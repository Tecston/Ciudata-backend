from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine, Column, Integer, Text, Date
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from dotenv import load_dotenv
import os, json

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:5000")

app = Flask(__name__)
CORS(app, resources={r"/reportes/*": {"origins": "*"}})

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

class Reporte(Base):
    __tablename__ = "reportes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    category = Column(Text)
    authorname = Column(Text)
    contactphone = Column(Text)
    imageurl = Column(Text)
    date = Column(Date)
    supports = Column(Integer, default=0)
    location = Column(Geography("POINT", srid=4326))

Base.metadata.create_all(engine)

def reporte_to_dict(r):
    p = to_shape(r.location)
    return {
        "id": r.id,
        "title": r.title,
        "description": r.description,
        "category": r.category,
        "authorName": r.authorname,
        "contactPhone": r.contactphone,
        "imageUrl": r.imageurl,
        "date": r.date.strftime("%Y-%m-%d") if r.date else None,
        "supports": r.supports,
        "location": {"lat": p.y, "lng": p.x},
    }

@app.route("/")
def root():
    return "API Flask + PostgreSQL/PostGIS OK"

@app.route("/reportes", methods=["POST"])
def create_reporte():
    session = Session()
    try:
        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]
        authorname = request.form["authorName"]
        contactphone = request.form.get("contactPhone", "")
        loc = json.loads(request.form.get("location", "{}"))
        lat, lng = float(loc.get("lat", 0)), float(loc.get("lng", 0))
        image = request.files.get("image")
        imageurl = ""
        if image:
            fname = secure_filename(image.filename)
            path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
            image.save(path)
            imageurl = f"{PUBLIC_URL}/uploads/{fname}"
        rep = Reporte(
            title=title,
            description=description,
            category=category,
            authorname=authorname,
            contactphone=contactphone,
            imageurl=imageurl,
            date=datetime.utcnow(),
            supports=0,
            location=from_shape(Point(lng, lat), srid=4326),
        )
        session.add(rep)
        session.commit()
        return jsonify({"mensaje": "Reporte creado", "reporte": reporte_to_dict(rep)}), 201
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()

@app.route("/reportes", methods=["GET"])
def list_reportes():
    session = Session()
    try:
        return jsonify([reporte_to_dict(r) for r in session.query(Reporte).all()])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@app.route("/reportes/<int:rep_id>", methods=["DELETE"])
def delete_reporte(rep_id):
    session = Session()
    try:
        rep = session.query(Reporte).get(rep_id)
        if not rep:
            return jsonify({"error": "Reporte no encontrado"}), 404
        session.delete(rep)
        session.commit()
        return jsonify({"mensaje": "Reporte eliminado"})
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
