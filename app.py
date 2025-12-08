import sqlite3
import os
from flask import Flask, render_template, request, url_for, redirect, session, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'cok_gizli_anahtar'

# --- AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def db_baglantisi_kur():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- FİLTRELER ---
@app.template_filter('okuma_suresi')
def okuma_suresi(metin):
    if not metin:
        return "1 dk"
    return f"{max(1, int(len(metin.split()) / 200))} dk"

# --- ROTALAR ---

@app.route("/")
def anasayfa():
    conn = db_baglantisi_kur()
    yazilar = conn.execute(
        'SELECT * FROM yazilar WHERE durum = 1 ORDER BY id DESC'
    ).fetchall()
    conn.close()
    return render_template("index.html", posts=yazilar)

@app.route('/<int:id>')
def detay(id):
    conn = db_baglantisi_kur()

    # Sayaç
    try:
        conn.execute(
            'UPDATE yazilar SET goruntulenme = goruntulenme + 1 WHERE id = ?',
            (id,)
        )
        conn.commit()
    except:
        pass

    # Yazı ve Yazar Bilgisi
    yazi = conn.execute(
        """
        SELECT yazilar.*, users.ad_soyad, users.profil_resmi, users.biyografi
        FROM yazilar
        JOIN users ON yazilar.author_id = users.id
        WHERE yazilar.id = ?
        """,
        (id,)
    ).fetchone()

    # Yorumlar
    try:
        yorumlar = conn.execute(
            """
            SELECT yorumlar.*, users.ad_soyad
            FROM yorumlar
            JOIN users ON yorumlar.user_id = users.id
            WHERE post_id = ?
            ORDER BY yorumlar.id DESC
            """,
            (id,)
        ).fetchall()
    except:
        yorumlar = []

    conn.close()

    if yazi is None:
        abort(404)

    return render_template('detay.html', yazi=yazi, yorumlar=yorumlar)

@app.route("/yeni", methods=('GET', 'POST'))
def yeni_yazi():
    if session.get('rol') not in ['admin', 'yazar']:
        return "Yetkisiz", 403

    if request.method == 'POST':
        baslik = request.form['baslik']
        icerik = request.form['icerik']
        kategori = request.form['kategori']
        resim = request.files.get('resim')

        resim_adi = ""
        if resim and resim.filename:
            resim_adi = secure_filename(resim.filename)
            resim.save(os.path.join(app.config['UPLOAD_FOLDER'], resim_adi))

        durum = 1 if session['rol'] == 'admin' else 0

        conn = db_baglantisi_kur()
        conn.execute(
            '''
            INSERT INTO yazilar (baslik, icerik, kategori, author_id, durum, resim)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (baslik, icerik, kategori, session['user_id'], durum, resim_adi)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('anasayfa'))

    return render_template('yeni.html')

@app.route('/<int:id>/duzenle', methods=('GET', 'POST'))
def duzenle(id):
    if not session.get('giris_yapildi'):
        return redirect(url_for('giris'))

    conn = db_baglantisi_kur()
    yazi = conn.execute(
        'SELECT * FROM yazilar WHERE id = ?',
        (id,)
    ).fetchone()

    if yazi is None:
        conn.close()
        abort(404)

    if session['rol'] != 'admin' and session['user_id'] != yazi['author_id']:
        conn.close()
        return "Yetkisiz", 403

    if request.method == 'POST':
        baslik = request.form['baslik']
        icerik = request.form['icerik']
        kategori = request.form['kategori']
        resim = request.files.get('resim')

        if resim and resim.filename:
            dosya = secure_filename(resim.filename)
            resim.save(os.path.join(app.config['UPLOAD_FOLDER'], dosya))
            conn.execute(
                'UPDATE yazilar SET baslik=?, icerik=?, kategori=?, resim=? WHERE id=?',
                (baslik, icerik, kategori, dosya, id)
            )
        else:
            conn.execute(
                'UPDATE yazilar SET baslik=?, icerik=?, kategori=? WHERE id=?',
                (baslik, icerik, kategori, id)
            )

        conn.commit()
        conn.close()
        return redirect(url_for('detay', id=id))

    conn.close()
    return render_template('duzenle.html', yazi=yazi)

# --- GİRİŞ / ÇIKIŞ / KAYIT ---
@app.route("/giris", methods=('GET', 'POST'))
def giris():
    if request.method == 'POST':
        email = request.form['email']
        sifre = request.form['sifre']

        conn = db_baglantisi_kur()
        user = conn.execute(
            'SELECT * FROM users WHERE email=?',
            (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user['sifre'], sifre):
            session['user_id'] = user['id']
            session['ad_soyad'] = user['ad_soyad']
            session['rol'] = user['rol']
            session['giris_yapildi'] = True

            if user['rol'] == 'admin':
                return redirect(url_for('admin_panel'))
            return redirect(url_for('anasayfa'))
        else:
            return render_template('giris.html', hata="E-posta veya şifre hatalı!")

    return render_template('giris.html')

@app.route("/kayit", methods=('GET', 'POST'))
def kayit():
    if request.method == 'POST':
        try:
            conn = db_baglantisi_kur()
            conn.execute(
                'INSERT INTO users (ad_soyad, email, sifre) VALUES (?,?,?)',
                (
                    request.form['ad_soyad'],
                    request.form['email'],
                    generate_password_hash(request.form['sifre'])
                )
            )
            conn.commit()
            conn.close()
            return redirect(url_for('giris'))
        except:
            return render_template('kayit.html', hata="Bu e-posta zaten kayıtlı!")

    return render_template('kayit.html')

@app.route("/cikis")
def cikis():
    session.clear()
    return redirect(url_for('anasayfa'))

# --- PROFİL VE YAZARLAR ---
@app.route('/profil-duzenle', methods=('GET', 'POST'))
def profil_duzenle():
    if not session.get('giris_yapildi'):
        return redirect(url_for('giris'))

    conn = db_baglantisi_kur()

    if request.method == 'POST':
        ad_soyad = request.form['ad_soyad']
        biyografi = request.form['biyografi']

        conn.execute(
            "UPDATE users SET ad_soyad=?, biyografi=? WHERE id=?",
            (ad_soyad, biyografi, session['user_id'])
        )
        conn.commit()
        session['ad_soyad'] = ad_soyad
        conn.close()
        return redirect(url_for('anasayfa'))

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session['user_id'],)
    ).fetchone()
    conn.close()

    if user is None:
        abort(404)

    return render_template('profil_duzenle.html', user=user)

@app.route('/yazarlar')
def yazarlar_sayfasi():
    conn = db_baglantisi_kur()
    yazarlar = conn.execute(
        "SELECT * FROM users WHERE rol IN ('admin', 'yazar')"
    ).fetchall()
    conn.close()
    return render_template("yazarlar.html", yazarlar=yazarlar)

# --- ARAMA ---
@app.route('/arama')
def arama():
    kelime = request.args.get('q', '').strip()
    conn = db_baglantisi_kur()

    if kelime:
        posts = conn.execute(
            """
            SELECT * FROM yazilar
            WHERE durum = 1
              AND (baslik LIKE ? OR icerik LIKE ?)
            ORDER BY id DESC
            """,
            (f"%{kelime}%", f"%{kelime}%")
        ).fetchall()
    else:
        posts = []

    conn.close()
    return render_template('arama.html', kelime=kelime, posts=posts)

# --- GALERİ ---
@app.route('/galeri', methods=('GET', 'POST'))
def galeri():
    # Gerekirse sadece girişlilere aç:
    # if not session.get('giris_yapildi'):
    #     return redirect(url_for('giris'))

    mesaj = None
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    if request.method == 'POST':
        dosyalar = request.files.getlist('dosyalar')
        kaydedilenler = []

        for f in dosyalar:
            if f and f.filename:
                fname = secure_filename(f.filename)
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                kaydedilenler.append(fname)

        if kaydedilenler:
            mesaj = f"{len(kaydedilenler)} adet resim yüklendi."
        else:
            mesaj = "Hiç dosya seçilmedi."

    try:
        resimler = sorted(os.listdir(app.config['UPLOAD_FOLDER']))
    except FileNotFoundError:
        resimler = []

    return render_template('galeri.html', resimler=resimler, mesaj=mesaj)

# --- ADMIN PANELİ ---
@app.route("/admin")
def admin_panel():
    if session.get('rol') != 'admin':
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

    users = conn.execute(
        "SELECT * FROM users ORDER BY ad_soyad"
    ).fetchall()

    # İletişim mesajları için tablo yoksa patlamasın
    try:
        mesajlar = conn.execute(
            "SELECT * FROM iletisim_mesajlari ORDER BY tarih DESC"
        ).fetchall()
    except:
        mesajlar = []

    conn.close()

    return render_template(
        "admin.html",
        bekleyenler=bekleyenler,
        users=users,
        mesajlar=mesajlar
    )

@app.route("/admin/onayla/<int:id>", methods=('POST',))
def onayla(id):
    if session.get('rol') == 'admin':
        conn = db_baglantisi_kur()
        conn.execute(
            "UPDATE yazilar SET durum=1 WHERE id=?",
            (id,)
        )
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

@app.route("/admin/rutbe/<int:user_id>/<rol>", methods=('POST',))
def admin_rutbe(user_id, rol):
    if session.get('rol') != 'admin':
        return "Yetkisiz", 403

    if rol not in ['okur', 'yazar']:
        return "Geçersiz rol", 400

    conn = db_baglantisi_kur()
    conn.execute(
        "UPDATE users SET rol=? WHERE id=?",
        (rol, user_id)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/<int:id>/sil', methods=('POST',))
def sil(id):
    if not session.get('giris_yapildi'):
        return redirect(url_for('giris'))

    conn = db_baglantisi_kur()
    conn.execute(
        "DELETE FROM yazilar WHERE id=?",
        (id,)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('anasayfa'))

# --- KATEGORİ SİSTEMİ ---
@app.route('/kategori/<isim>')
def kategori_sayfasi(isim):
    conn = db_baglantisi_kur()
    yazilar = conn.execute(
        'SELECT * FROM yazilar WHERE kategori = ? AND durum = 1 ORDER BY id DESC',
        (isim,)
    ).fetchall()
    conn.close()
    return render_template("index.html", posts=yazilar)

# --- CKEDITOR RESİM YÜKLEME ---
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'upload' not in request.files:
        return jsonify({'error': 'Dosya yok'})

    f = request.files['upload']
    fname = secure_filename(f.filename)
    f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))

    return jsonify({
        'uploaded': 1,
        'fileName': fname,
        'url': url_for('static', filename='uploads/' + fname)
    })

# --- SABİT SAYFALAR ---
@app.route('/hakkimizda')
def hakkimizda():
    return render_template('hakkimizda.html')  # dosya adın nasıl ise ona göre düzelt

@app.route('/iletisim', methods=('GET', 'POST'))
def iletisim():
    if request.method == 'POST':
        isim = request.form['isim']
        email = request.form['email']
        konu = request.form['konu']
        mesaj = request.form['mesaj']

        # Şimdilik sadece başarı mesajı gösteriyoruz.
        # İstersen buraya DB'ye kaydetme logic'i ekleyebilirsin.
        return render_template('iletisim.html', basarili=True)

    return render_template('iletisim.html', basarili=False)

# --- TAMİR ROTASI ---
@app.route('/tamir')
def tamir_et():
    conn = db_baglantisi_kur()
    mesaj = []

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS yorumlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER,
                user_id INTEGER,
                yorum TEXT,
                tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        mesaj.append("✅ Yorumlar OK")
    except:
        pass

    try:
        conn.execute(
            "ALTER TABLE yazilar ADD COLUMN goruntulenme INTEGER DEFAULT 0"
        )
        conn.commit()
        mesaj.append("✅ İzlenme OK")
    except:
        pass

    try:
        conn.execute(
            "ALTER TABLE users ADD COLUMN profil_resmi TEXT"
        )
        conn.commit()
        mesaj.append("✅ Profil OK")
    except:
        pass

    try:
        conn.execute(
            "ALTER TABLE users ADD COLUMN biyografi TEXT"
        )
        conn.commit()
        mesaj.append("✅ Biyo OK")
    except:
        pass

    conn.close()
    return "<br>".join(mesaj)

if __name__ == "__main__":
    app.run(debug=True)