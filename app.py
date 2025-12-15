import sqlite3
import os
from flask import Flask, render_template, request, url_for, redirect, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'cok_gizli_anahtar'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def db_baglantisi_kur():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.template_filter('okuma_suresi')
def okuma_suresi(metin):
    if not metin:
        return "1 dk"
    return f"{max(1, int(len(metin.split()) / 200))} dk"


@app.route("/")
def anasayfa():
    conn = db_baglantisi_kur()
    yazilar = conn.execute("SELECT * FROM yazilar WHERE durum = 1 ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("index.html", posts=yazilar)


@app.route("/<int:id>")
def detay(id):
    conn = db_baglantisi_kur()

    # görüntülenme +1
    try:
        conn.execute("UPDATE yazilar SET goruntulenme = COALESCE(goruntulenme,0) + 1 WHERE id = ?", (id,))
        conn.commit()
    except Exception as e:
        print("Goruntulenme hatası:", e)

    yazi = conn.execute("""
        SELECT yazilar.*, users.ad_soyad, users.profil_resmi, users.biyografi
        FROM yazilar
        JOIN users ON yazilar.author_id = users.id
        WHERE yazilar.id = ?
    """, (id,)).fetchone()

    if yazi is None:
        conn.close()
        abort(404)

    # Ana yorumlar (parent_id NULL veya 0)
    try:
        yorumlar = conn.execute("""
            SELECT yorumlar.*, users.ad_soyad
            FROM yorumlar
            JOIN users ON yorumlar.user_id = users.id
            WHERE post_id = ? AND (parent_id IS NULL OR parent_id = 0)
            ORDER BY id DESC
        """, (id,)).fetchall()
    except Exception as e:
        print("Ana yorumları çekerken hata:", e)
        yorumlar = []

    # Cevaplar (parent_id dolu)
    try:
        cevaplar = conn.execute("""
            SELECT yorumlar.*, users.ad_soyad
            FROM yorumlar
            JOIN users ON yorumlar.user_id = users.id
            WHERE post_id = ? AND parent_id IS NOT NULL AND parent_id != 0
            ORDER BY id ASC
        """, (id,)).fetchall()
    except Exception as e:
        print("Cevapları çekerken hata:", e)
        cevaplar = []

    cevap_map = {}
    for c in cevaplar:
        cevap_map.setdefault(c["parent_id"], []).append(c)

    conn.close()
    return render_template("detay.html", yazi=yazi, yorumlar=yorumlar, cevap_map=cevap_map)


@app.route("/yorum-ekle/<int:post_id>", methods=["POST"])
def yorum_ekle(post_id):
    if not session.get("giris_yapildi"):
        return redirect(url_for("giris"))

    yorum_metin = request.form.get("yorum", "").strip()
    if not yorum_metin:
        return redirect(url_for("detay", id=post_id))

    conn = db_baglantisi_kur()
    conn.execute(
        "INSERT INTO yorumlar (post_id, user_id, yorum, parent_id) VALUES (?, ?, ?, NULL)",
        (post_id, session["user_id"], yorum_metin)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("detay", id=post_id))


@app.route("/yorum-yanitla/<int:post_id>/<int:parent_id>", methods=["POST"])
def yorum_yanitla(post_id, parent_id):
    if not session.get("giris_yapildi"):
        return redirect(url_for("giris"))

    metin = request.form.get("yorum", "").strip()
    if not metin:
        return redirect(url_for("detay", id=post_id))

    conn = db_baglantisi_kur()
    conn.execute(
        "INSERT INTO yorumlar (post_id, user_id, yorum, parent_id) VALUES (?, ?, ?, ?)",
        (post_id, session["user_id"], metin, parent_id)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("detay", id=post_id))


@app.route("/yorum-sil/<int:yorum_id>", methods=["POST"])
def yorum_sil(yorum_id):
    if not session.get("giris_yapildi"):
        return redirect(url_for("giris"))

    conn = db_baglantisi_kur()
    yorum = conn.execute("SELECT * FROM yorumlar WHERE id=?", (yorum_id,)).fetchone()
    if yorum is None:
        conn.close()
        abort(404)

    if session.get("rol") != "admin" and session.get("user_id") != yorum["user_id"]:
        conn.close()
        return "Yetkisiz", 403

    # yorumu + cevaplarını sil
    conn.execute("DELETE FROM yorumlar WHERE id=? OR parent_id=?", (yorum_id, yorum_id))
    conn.commit()
    post_id = yorum["post_id"]
    conn.close()
    return redirect(url_for("detay", id=post_id))


@app.route("/yorum-duzenle/<int:yorum_id>", methods=["GET", "POST"])
def yorum_duzenle(yorum_id):
    if not session.get("giris_yapildi"):
        return redirect(url_for("giris"))

    conn = db_baglantisi_kur()
    yorum = conn.execute("SELECT * FROM yorumlar WHERE id=?", (yorum_id,)).fetchone()
    if yorum is None:
        conn.close()
        abort(404)

    if session.get("rol") != "admin" and session.get("user_id") != yorum["user_id"]:
        conn.close()
        return "Yetkisiz", 403

    if request.method == "POST":
        yeni = request.form.get("yorum", "").strip()
        if yeni:
            conn.execute("UPDATE yorumlar SET yorum=? WHERE id=?", (yeni, yorum_id))
            conn.commit()
        post_id = yorum["post_id"]
        conn.close()
        return redirect(url_for("detay", id=post_id))

    conn.close()
    return render_template("yorum_duzenle.html", yorum=yorum)

# --- diğer route'ların sende kalabilir (giris/kayit/yeni/admin/upload vs.) ---