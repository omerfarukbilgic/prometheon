import sqlite3
import os
from flask import Flask, render_template, request, url_for, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64

# --- AYARLAR ---
app = Flask(__name__)
app.secret_key = 'cok_gizli_anahtar_buraya'

# RESİM YÜKLEME AYARLARI
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Klasör yoksa oluştur (Hata vermemesi için)
os.makedirs(os.path.join(app.root_path, 'static/uploads'), exist_ok=True)

# --- FİLTRELER ---
def okuma_suresi_hesapla(metin):
    if not metin: return "1 dk"
    kelime_sayisi = len(metin.split())
    dakika = int(kelime_sayisi / 200)
    if dakika == 0: return "1 dk"
    return f"{dakika} dk"

app.jinja_env.filters['okuma_suresi'] = okuma_suresi_hesapla

def db_baglantisi_kur():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- ROTALAR ---

@app.route("/")
def anasayfa():
    conn = db_baglantisi_kur()
    yazilar = conn.execute('SELECT * FROM yazilar WHERE durum = 1 ORDER BY id DESC').fetchall()
    conn.close()
    return render_template("index.html", posts=yazilar)

@app.route('/kategori/<isim>')
def kategori_sayfasi(isim):
    conn = db_baglantisi_kur()
    yazilar = conn.execute('SELECT * FROM yazilar WHERE kategori = ? AND durum = 1 ORDER BY id DESC', (isim,)).fetchall()
    conn.close()
    return render_template("index.html", posts=yazilar)

@app.route('/ara')
def ara():
    kelime = request.args.get('q')
    if not kelime: return redirect(url_for('anasayfa'))
    conn = db_baglantisi_kur()
    sonuclar = conn.execute("SELECT * FROM yazilar WHERE (baslik LIKE ? OR icerik LIKE ?) AND durum = 1 ORDER BY id DESC", ('%'+kelime+'%', '%'+kelime+'%')).fetchall()
    conn.close()
    return render_template('arama.html', kelime=kelime, posts=sonuclar)

@app.route('/<int:id>')
def detay(id):
    conn = db_baglantisi_kur()
    sorgu = "SELECT yazilar.*, users.ad_soyad, users.profil_resmi, users.biyografi FROM yazilar JOIN users ON yazilar.author_id = users.id WHERE yazilar.id = ?"
    yazi = conn.execute(sorgu, (id,)).fetchone()
    yorumlar = conn.execute("SELECT yorumlar.*, users.ad_soyad FROM yorumlar JOIN users ON yorumlar.user_id = users.id WHERE post_id = ? ORDER BY id DESC", (id,)).fetchall()
    conn.close()
    return render_template('detay.html', yazi=yazi, yorumlar=yorumlar)

# --- YENİ YAZI (RESİM YÜKLEMELİ) ---
@app.route("/yeni", methods=('GET', 'POST'))
def yeni_yazi():
    if session.get('rol') not in ['admin', 'yazar']:
        return "Yetkiniz yok", 403

    if request.method == 'POST':
        baslik = request.form['baslik']
        icerik = request.form['icerik']
        kategori = request.form['kategori']
        
        # RESİM İŞLEMLERİ
        resim_dosyasi = request.files.get('resim') # Formdan dosyayı al (varsa)
        resim_adi = "" 
        
        if resim_dosyasi and resim_dosyasi.filename != '':
            dosya_adi = secure_filename(resim_dosyasi.filename)
            resim_dosyasi.save(os.path.join(app.config['UPLOAD_FOLDER'], dosya_adi))
            resim_adi = dosya_adi # Veritabanına sadece ismini kaydediyoruz

        durum = 1 if session['rol'] == 'admin' else 0
        
        conn = db_baglantisi_kur()
        conn.execute('INSERT INTO yazilar (baslik, icerik, kategori, author_id, durum, resim) VALUES (?, ?, ?, ?, ?, ?)', 
                     (baslik, icerik, kategori, session['user_id'], durum, resim_adi))
        conn.commit()
        conn.close()
        
        if durum == 0:
            return "<h1>Yazınız editör onayına gönderildi!</h1><a href='/'>Anasayfaya Dön</a>"
        return redirect(url_for('anasayfa'))

    return render_template('yeni.html')

# --- DİĞER FONKSİYONLAR (Giriş, Çıkış, Admin vb.) ---
# (Önceki kodların aynısı buraya gelecek, yer kaplamasın diye hepsini tekrar yazmadım ama sen 
# SİLMEDİYSEN duruyordur. SİLDİYSEN SÖYLE TAMAMINI ATAYIM)

@app.route("/giris", methods=('GET', 'POST'))
def giris():
    if request.method == 'POST':
        email = request.form['email']
        sifre = request.form['sifre']
        conn = db_baglantisi_kur()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user['sifre'], sifre):
            session['user_id'] = user['id']
            session['ad_soyad'] = user['ad_soyad']
            session['rol'] = user['rol']
            session['giris_yapildi'] = True
            if user['rol'] == 'admin': return redirect(url_for('admin_panel'))
            else: return redirect(url_for('anasayfa'))
        else: return render_template('giris.html', hata="Hatalı bilgi!")
    return render_template('giris.html')

@app.route("/kayit", methods=('GET', 'POST'))
def kayit():
    if request.method == 'POST':
        ad_soyad = request.form['ad_soyad']
        email = request.form['email']
        sifre = generate_password_hash(request.form['sifre'])
        try:
            conn = db_baglantisi_kur()
            conn.execute('INSERT INTO users (ad_soyad, email, sifre) VALUES (?, ?, ?)', (ad_soyad, email, sifre))
            conn.commit()
            conn.close()
            return redirect(url_for('giris'))
        except: return render_template('kayit.html', hata="Bu e-posta kayıtlı!")
    return render_template('kayit.html')

@app.route("/cikis")
def cikis():
    session.clear()
    return redirect(url_for('anasayfa'))

@app.route("/admin")
def admin_panel():
    if session.get('rol') != 'admin': return "Yetkisiz", 403
    conn = db_baglantisi_kur()
    bekleyenler = conn.execute("SELECT yazilar.*, users.ad_soyad as yazar_adi FROM yazilar JOIN users ON yazilar.author_id = users.id WHERE durum = 0").fetchall()
    users = conn.execute("SELECT * FROM users").fetchall()
    mesajlar = conn.execute("SELECT * FROM mesajlar ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin.html", bekleyenler=bekleyenler, users=users, mesajlar=mesajlar)

@app.route("/admin/onayla/<int:id>", methods=('POST',))
def onayla(id):
    if session.get('rol') == 'admin':
        conn = db_baglantisi_kur()
        conn.execute("UPDATE yazilar SET durum = 1 WHERE id = ?", (id,))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

@app.route("/admin/rutbe/<int:id>/<yeni_rol>", methods=('POST',))
def rutbe_degistir(id, yeni_rol):
    if session.get('rol') == 'admin':
        conn = db_baglantisi_kur()
        conn.execute("UPDATE users SET rol = ? WHERE id = ?", (yeni_rol, id))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/yazarlar')
def yazarlar_sayfasi():
    conn = db_baglantisi_kur()
    yazarlar = conn.execute("SELECT * FROM users WHERE rol IN ('admin', 'yazar')").fetchall()
    conn.close()
    return render_template("yazarlar.html", yazarlar=yazarlar)

@app.route('/yazar/<int:id>')
def yazar_profili(id):
    conn = db_baglantisi_kur()
    yazar = conn.execute("SELECT * FROM users WHERE id = ?", (id,)).fetchone()
    yazilar = conn.execute("SELECT * FROM yazilar WHERE author_id = ? AND durum = 1 ORDER BY id DESC", (id,)).fetchall()
    conn.close()
    return render_template("index.html", posts=yazilar)

@app.route('/profil-duzenle', methods=('GET', 'POST'))
def profil_duzenle():
    if not session.get('giris_yapildi'): return redirect(url_for('giris'))
    conn = db_baglantisi_kur()
    if request.method == 'POST':
        ad_soyad = request.form['ad_soyad']
        biyografi = request.form['biyografi']
        profil_resmi = request.form['profil_resmi'] 
        conn.execute("UPDATE users SET ad_soyad=?, biyografi=?, profil_resmi=? WHERE id=?", (ad_soyad, biyografi, profil_resmi, session['user_id']))
        conn.commit()
        session['ad_soyad'] = ad_soyad
        conn.close()
        return redirect(url_for('yazarlar_sayfasi'))
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    conn.close()
    return render_template('profil_duzenle.html', user=user)

@app.route('/hakkimizda')
def hakkimizda(): return render_template('hakkimizda.html')

@app.route('/iletisim', methods=('GET', 'POST'))
def iletisim():
    if request.method == 'POST':
        isim = request.form['isim']
        email = request.form['email']
        konu = request.form['konu']
        mesaj = request.form['mesaj']
        conn = db_baglantisi_kur()
        conn.execute("INSERT INTO mesajlar (isim, email, konu, mesaj) VALUES (?, ?, ?, ?)", (isim, email, konu, mesaj))
        conn.commit()
        conn.close()
        return render_template('iletisim.html', basarili=True)
    return render_template('iletisim.html')

# --- SİLME VE DÜZENLEME ---
@app.route('/<int:id>/duzenle', methods=('GET', 'POST'))
def duzenle(id):
    if not session.get('giris_yapildi'): return redirect(url_for('giris'))
    conn = db_baglantisi_kur()
    yazi = conn.execute('SELECT * FROM yazilar WHERE id = ?', (id,)).fetchone()
    if session['rol'] != 'admin' and session['user_id'] != yazi['author_id']:
        conn.close()
        return "Yetkiniz yok", 403
    if request.method == 'POST':
        baslik = request.form['baslik']
        icerik = request.form['icerik']
        kategori = request.form['kategori']
        conn.execute('UPDATE yazilar SET baslik = ?, icerik = ?, kategori = ? WHERE id = ?', (baslik, icerik, kategori, id))
        conn.commit()
        conn.close()
        return redirect(url_for('detay', id=id))
    conn.close()
    return render_template('duzenle.html', yazi=yazi)

@app.route('/<int:id>/sil', methods=('POST',))
def sil(id):
    if not session.get('giris_yapildi'): return redirect(url_for('giris'))
    conn = db_baglantisi_kur()
    yazi = conn.execute('SELECT * FROM yazilar WHERE id = ?', (id,)).fetchone()
    if session['rol'] != 'admin' and session['user_id'] != yazi['author_id']:
        conn.close()
        return "Yetkiniz yok", 403
    conn.execute('DELETE FROM yazilar WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('anasayfa'))

if __name__ == "__main__":
    app.run(debug=True, port=5001)