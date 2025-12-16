import os
import sqlite3
from flask import Flask, render_template, request, url_for, redirect, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "cok_gizli_anahtar"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def db_baglantisi_kur():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def tablo_sutun_var_mi(conn, tablo_adi, sutun_adi) -> bool:
    try:
        cols = conn.execute(f"PRAGMA table_info({tablo_adi})").fetchall()
        return any(c["name"] == sutun_adi for c in cols)
    except Exception:
        return False


# --- FİLTRE ---
@app.template_filter("okuma_suresi")
def okuma_suresi(metin):
    if not metin:
        return "1 dk"
    return f"{max(1, int(len(metin.split()) / 200))} dk"


# --- ANASAYFA ---
@app.route("/")
def anasayfa():
    conn = db_baglantisi_kur()
    yazilar = conn.execute("SELECT * FROM yazilar WHERE durum = 1 ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("index.html", posts=yazilar)


# --- DETAY + YORUMLAR ---
@app.route("/<int:id>")
def detay(id):
    conn = db_baglantisi_kur()

    # görüntülenme
    try:
        if tablo_sutun_var_mi(conn, "yazilar", "goruntulenme"):
            conn.execute("UPDATE yazilar SET goruntulenme = goruntulenme + 1 WHERE id = ?", (id,))
            conn.commit()
    except Exception as e:
        print("goruntulenme hata:", e)

    yazi = conn.execute(
        """
        SELECT yazilar.*, users.ad_soyad
        FROM yazilar
        JOIN users ON yazilar.author_id = users.id
        WHERE yazilar.id = ?
        """,
        (id,),
    ).fetchone()

    if yazi is None:
        conn.close()
        abort(404)

    # parent_id var mı?
    parent_ok = tablo_sutun_var_mi(conn, "yorumlar", "parent_id")

    if parent_ok:
        # ana yorumlar
        yorumlar = conn.execute(
            """
            SELECT yorumlar.*, users.ad_soyad
            FROM yorumlar
            JOIN users ON yorumlar.user_id = users.id
            WHERE post_id = ? AND (parent_id IS NULL OR parent_id = 0)
            ORDER BY id DESC
            """,
            (id,),
        ).fetchall()

        # cevaplar
        cevaplar = conn.execute(
            """
            SELECT yorumlar.*, users.ad_soyad
            FROM yorumlar
            JOIN users ON yorumlar.user_id = users.id
            WHERE post_id = ? AND parent_id IS NOT NULL AND parent_id != 0
            ORDER BY id ASC
            """,
            (id,),
        ).fetchall()

        cevap_map = {}
        for c in cevaplar:
            cevap_map.setdefault(c["parent_id"], []).append(c)
    else:
        # eski sistem (parent yok)
        yorumlar = conn.execute(
            """
            SELECT yorumlar.*, users.ad_soyad
            FROM yorumlar
            JOIN users ON yorumlar.user_id = users.id
            WHERE post_id = ?
            ORDER BY id DESC
            """,
            (id,),
        ).fetchall()
        cevap_map = {}

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
    parent_ok = tablo_sutun_var_mi(conn, "yorumlar", "parent_id")

    if parent_ok:
        conn.execute(
            "INSERT INTO yorumlar (post_id, user_id, yorum, parent_id) VALUES (?, ?, ?, NULL)",
            (post_id, session["user_id"], yorum_metin),
        )
    else:
        conn.execute(
            "INSERT INTO yorumlar (post_id, user_id, yorum) VALUES (?, ?, ?)",
            (post_id, session["user_id"], yorum_metin),
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
    parent_ok = tablo_sutun_var_mi(conn, "yorumlar", "parent_id")
    if not parent_ok:
        conn.close()
        return redirect(url_for("detay", id=post_id))

    conn.execute(
        "INSERT INTO yorumlar (post_id, user_id, yorum, parent_id) VALUES (?, ?, ?, ?)",
        (post_id, session["user_id"], metin, parent_id),
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

    parent_ok = tablo_sutun_var_mi(conn, "yorumlar", "parent_id")

    if parent_ok:
        # yorumu + cevaplarını sil
        conn.execute("DELETE FROM yorumlar WHERE id=? OR parent_id=?", (yorum_id, yorum_id))
    else:
        conn.execute("DELETE FROM yorumlar WHERE id=?", (yorum_id,))

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


# --- YENİ YAZI / DÜZENLE / SİL ---
@app.route("/yeni", methods=("GET", "POST"))
def yeni_yazi():
    if session.get("rol") not in ["admin", "yazar"]:
        return "Yetkisiz", 403

    if request.method == "POST":
        baslik = request.form["baslik"]
        icerik = request.form["icerik"]
        kategori = request.form["kategori"]
        resim = request.files.get("resim")

        resim_adi = ""
        if resim and resim.filename:
            resim_adi = secure_filename(resim.filename)
            resim.save(os.path.join(app.config["UPLOAD_FOLDER"], resim_adi))

        durum = 1 if session["rol"] == "admin" else 0

        conn = db_baglantisi_kur()
        conn.execute(
            """
            INSERT INTO yazilar (baslik, icerik, kategori, author_id, durum, resim)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (baslik, icerik, kategori, session["user_id"], durum, resim_adi),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("anasayfa"))

    return render_template("yeni.html")


@app.route("/<int:id>/duzenle", methods=("GET", "POST"))
def duzenle(id):
    if not session.get("giris_yapildi"):
        return redirect(url_for("giris"))

    conn = db_baglantisi_kur()
    yazi = conn.execute("SELECT * FROM yazilar WHERE id = ?", (id,)).fetchone()
    if yazi is None:
        conn.close()
        abort(404)

    if session["rol"] != "admin" and session["user_id"] != yazi["author_id"]:
        conn.close()
        return "Yetkisiz", 403

    if request.method == "POST":
        baslik = request.form["baslik"]
        icerik = request.form["icerik"]
        kategori = request.form["kategori"]
        resim = request.files.get("resim")

        if resim and resim.filename:
            dosya = secure_filename(resim.filename)
            resim.save(os.path.join(app.config["UPLOAD_FOLDER"], dosya))
            conn.execute(
                "UPDATE yazilar SET baslik=?, icerik=?, kategori=?, resim=? WHERE id=?",
                (baslik, icerik, kategori, dosya, id),
            )
        else:
            conn.execute(
                "UPDATE yazilar SET baslik=?, icerik=?, kategori=? WHERE id=?",
                (baslik, icerik, kategori, id),
            )

        conn.commit()
        conn.close()
        return redirect(url_for("detay", id=id))

    conn.close()
    return render_template("duzenle.html", yazi=yazi)


@app.route("/<int:id>/sil", methods=("POST",))
def sil(id):
    if not session.get("giris_yapildi"):
        return redirect(url_for("giris"))

    conn = db_baglantisi_kur()
    conn.execute("DELETE FROM yazilar WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("anasayfa"))


# --- GİRİŞ / KAYIT / ÇIKIŞ ---
@app.route("/giris", methods=("GET", "POST"))
def giris():
    if request.method == "POST":
        email = request.form["email"]
        sifre = request.form["sifre"]

        conn = db_baglantisi_kur()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["sifre"], sifre):
            session["user_id"] = user["id"]
            session["ad_soyad"] = user["ad_soyad"]
            session["rol"] = user["rol"]
            session["giris_yapildi"] = True

            if user["rol"] == "admin":
                return redirect(url_for("admin_panel"))
            return redirect(url_for("anasayfa"))

        return render_template("giris.html", hata="E-posta veya şifre hatalı!")

    return render_template("giris.html")


@app.route("/kayit", methods=("GET", "POST"))
def kayit():
    if request.method == "POST":
        try:
            conn = db_baglantisi_kur()
            conn.execute(
                "INSERT INTO users (ad_soyad, email, sifre) VALUES (?,?,?)",
                (
                    request.form["ad_soyad"],
                    request.form["email"],
                    generate_password_hash(request.form["sifre"]),
                ),
            )
            conn.commit()
            conn.close()
            return redirect(url_for("giris"))
        except Exception:
            return render_template("kayit.html", hata="Bu e-posta zaten kayıtlı!")

    return render_template("kayit.html")


@app.route("/cikis")
def cikis():
    session.clear()
    return redirect(url_for("anasayfa"))


# --- PROFİL / YAZARLAR ---
@app.route("/profil-duzenle", methods=("GET", "POST"))
def profil_duzenle():
    if not session.get("giris_yapildi"):
        return redirect(url_for("giris"))

    conn = db_baglantisi_kur()

    if request.method == "POST":
        ad_soyad = request.form["ad_soyad"]
        biyografi = request.form.get("biyografi", "")
        profil_resmi = request.files.get("profil_resmi")

        if profil_resmi and profil_resmi.filename:
            fname = secure_filename(profil_resmi.filename)
            profil_resmi.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
            conn.execute(
                "UPDATE users SET ad_soyad=?, biyografi=?, profil_resmi=? WHERE id=?",
                (ad_soyad, biyografi, fname, session["user_id"]),
            )
        else:
            conn.execute(
                "UPDATE users SET ad_soyad=?, biyografi=? WHERE id=?",
                (ad_soyad, biyografi, session["user_id"]),
            )

        conn.commit()
        session["ad_soyad"] = ad_soyad
        conn.close()
        return redirect(url_for("anasayfa"))

    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    return render_template("profil_duzenle.html", user=user)


@app.route("/yazarlar")
def yazarlar_sayfasi():
    conn = db_baglantisi_kur()
    yazarlar = conn.execute("SELECT * FROM users WHERE rol IN ('admin','yazar')").fetchall()
    conn.close()
    return render_template("yazarlar.html", yazarlar=yazarlar)


@app.route("/yazar/<int:id>")
def yazar_profili(id):
    conn = db_baglantisi_kur()
    yazar = conn.execute("SELECT * FROM users WHERE id=?", (id,)).fetchone()
    if yazar is None:
        conn.close()
        abort(404)

    yazilar = conn.execute(
        "SELECT * FROM yazilar WHERE author_id=? AND durum=1 ORDER BY id DESC",
        (id,),
    ).fetchall()

    conn.close()
    return render_template("yazar_detay.html", yazar=yazar, yazilar=yazilar)


# --- KATEGORİ ---
@app.route("/kategori/<isim>")
def kategori_sayfasi(isim):
    conn = db_baglantisi_kur()
    yazilar = conn.execute(
        "SELECT * FROM yazilar WHERE kategori=? AND durum=1 ORDER BY id DESC",
        (isim,),
    ).fetchall()
    conn.close()
    return render_template("index.html", posts=yazilar)


# --- ARAMA ---
@app.route("/arama")
def arama():
    kelime = request.args.get("q", "").strip()
    conn = db_baglantisi_kur()

    if kelime:
        posts = conn.execute(
            """
            SELECT * FROM yazilar
            WHERE durum = 1 AND (baslik LIKE ? OR icerik LIKE ?)
            ORDER BY id DESC
            """,
            (f"%{kelime}%", f"%{kelime}%"),
        ).fetchall()
    else:
        posts = []

    conn.close()
    return render_template("arama.html", kelime=kelime, posts=posts)


# --- CKEDITOR UPLOAD ---
@app.route("/upload", methods=["POST"])
def upload_file():
    if "upload" not in request.files:
        return "No file part", 400

    f = request.files["upload"]
    if f.filename == "":
        return "No selected file", 400

    fname = secure_filename(f.filename)
    f.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
    file_url = url_for("static", filename="uploads/" + fname)

    callback = request.args.get("CKEditorFuncNum")
    return f"<script>window.parent.CKEDITOR.tools.callFunction({callback}, '{file_url}', '');</script>"


# --- ADMIN ---
@app.route("/admin")
def admin_panel():
    if session.get("rol") != "admin":
        return "Yetkisiz", 403

    conn = db_baglantisi_kur()

    bekleyenler = conn.execute(
        """
        SELECT yazilar.*, users.ad_soyad AS yazar_adi
        FROM yazilar
        JOIN users ON yazilar.author_id = users.id
        WHERE yazilar.durum = 0
        ORDER BY yazilar.id DESC
        """
    ).fetchall()

    users = conn.execute("SELECT * FROM users ORDER BY ad_soyad").fetchall()

    # iletişim tablon yoksa patlamasın
    try:
        mesajlar = conn.execute("SELECT * FROM iletisim_mesajlari ORDER BY tarih DESC").fetchall()
    except Exception:
        mesajlar = []

    conn.close()
    return render_template("admin.html", bekleyenler=bekleyenler, users=users, mesajlar=mesajlar)


@app.route("/admin/onayla/<int:id>", methods=("POST",))
def onayla(id):
    if session.get("rol") != "admin":
        return "Yetkisiz", 403

    conn = db_baglantisi_kur()
    conn.execute("UPDATE yazilar SET durum=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_panel"))


@app.route("/admin/rutbe/<int:user_id>/<rol>", methods=("POST",))
def admin_rutbe(user_id, rol):
    if session.get("rol") != "admin":
        return "Yetkisiz", 403

    if rol not in ["okur", "yazar"]:
        return "Geçersiz rol", 400

    conn = db_baglantisi_kur()
    conn.execute("UPDATE users SET rol=? WHERE id=?", (rol, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_panel"))


# --- SABİT SAYFALAR ---
@app.route("/hakkimizda")
def hakkimizda():
    return render_template("hakkimizda.html")


@app.route("/iletisim", methods=("GET", "POST"))
def iletisim():
    if request.method == "POST":
        # şu an sadece mesaj gösteriyorsun
        return render_template("iletisim.html", basarili=True)
    return render_template("iletisim.html", basarili=False)


# --- TAMİR ---
@app.route("/tamir")
def tamir_et():
    conn = db_baglantisi_kur()
    mesaj = []

    # yorumlar tablosu
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS yorumlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER,
                user_id INTEGER,
                yorum TEXT,
                tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        mesaj.append("✅ yorumlar tablo OK")
    except Exception as e:
        mesaj.append(f"❌ yorumlar tablo hata: {e}")

    # parent_id yoksa ekle
    try:
        if not tablo_sutun_var_mi(conn, "yorumlar", "parent_id"):
            conn.execute("ALTER TABLE yorumlar ADD COLUMN parent_id INTEGER")
            conn.commit()
        mesaj.append("✅ parent_id OK")
    except Exception as e:
        mesaj.append(f"❌ parent_id hata: {e}")

    # goruntulenme
    try:
        if not tablo_sutun_var_mi(conn, "yazilar", "goruntulenme"):
            conn.execute("ALTER TABLE yazilar ADD COLUMN goruntulenme INTEGER DEFAULT 0")
            conn.commit()
        mesaj.append("✅ goruntulenme OK")
    except Exception as e:
        mesaj.append(f"❌ goruntulenme hata: {e}")

    # profil_resmi
    try:
        if not tablo_sutun_var_mi(conn, "users", "profil_resmi"):
            conn.execute("ALTER TABLE users ADD COLUMN profil_resmi TEXT")
            conn.commit()
        mesaj.append("✅ profil_resmi OK")
    except Exception as e:
        mesaj.append(f"❌ profil_resmi hata: {e}")

    # biyografi
    try:
        if not tablo_sutun_var_mi(conn, "users", "biyografi"):
            conn.execute("ALTER TABLE users ADD COLUMN biyografi TEXT")
            conn.commit()
        mesaj.append("✅ biyografi OK")
    except Exception as e:
        mesaj.append(f"❌ biyografi hata: {e}")

    conn.close()
    return "<br>".join(mesaj)


if __name__ == "__main__":
    app.run(debug=True)