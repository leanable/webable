import os
from flask import Flask, request, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
import vercel_blob  # pip install vercel-blob

app = Flask(__name__, template_folder="../templates")

# --- Database (Vercel Postgres / Neon / Supabase) ---
# On Vercel, POSTGRES_URL is injected automatically if you add a Postgres store.
# Fix the scheme for SQLAlchemy: postgres:// -> postgresql://
_db_url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
if _db_url and _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class FileUpload(db.Model):
    __tablename__ = "file_uploads"
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(1024), nullable=False)  # blob URL


# Create tables at import time (Vercel cold start)
with app.app_context():
    db.create_all()


@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            return redirect(request.url)

        # Upload to Vercel Blob
        blob = vercel_blob.put(
            file.filename,
            file.read(),
            {"addRandomSuffix": "true"},
        )
        blob_url = blob["url"]

        db.session.add(FileUpload(filename=file.filename, url=blob_url))
        db.session.commit()
        return redirect(url_for("upload_file"))

    files = FileUpload.query.order_by(FileUpload.id.desc()).all()
    return render_template("upload.html", files=files)


@app.route("/delete/<int:file_id>", methods=["POST"])
def delete_file(file_id):
    f = FileUpload.query.get_or_404(file_id)
    try:
        vercel_blob.delete(f.url)
    except Exception:
        pass  # blob may already be gone
    db.session.delete(f)
    db.session.commit()
    return redirect(url_for("upload_file"))


# Local dev entry point (not used by Vercel)
if __name__ == "__main__":
    app.run(debug=True)
