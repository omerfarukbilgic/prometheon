import sqlite3
from werkzeug.security import generate_password_hash

connection = sqlite3.connect('database.db')
cur = connection.cursor()

# Temizlik
# ... (Bağlantı kodları) ...

# Temizlik (ŞİMDİ MESAJLAR TABLOSUNU DA EKLEDİK)
cur.execute("DROP TABLE IF EXISTS yorumlar")
cur.execute("DROP TABLE IF EXISTS yazilar")
cur.execute("DROP TABLE IF EXISTS users")
cur.execute("DROP TABLE IF EXISTS mesajlar")  # <-- Eksik olan komut buydu!

# 1. KULLANICILAR TABLOSU (Şimdi CREATE komutlarına geçebiliriz)
# ...

# 1. KULLANICILAR TABLOSU (Biyografi ve Fotoğraf sütunu eklendi)
cur.execute("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_soyad TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    sifre TEXT NOT NULL,
    rol TEXT DEFAULT 'okur',
    profil_resmi TEXT DEFAULT '',
    biyografi TEXT DEFAULT 'Henüz bir biyografi eklenmemiş.'
)
""")

# 2. YAZILAR TABLOSU
# 2. YAZILAR TABLOSU (GÜNCELLENDİ: 'resim' sütunu eklendi)
cur.execute("""
CREATE TABLE yazilar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL,
    baslik TEXT NOT NULL,
    icerik TEXT NOT NULL,
    kategori TEXT NOT NULL,
    resim TEXT,  -- YENİ EKLENEN SÜTUN (Resim dosya adı burada duracak)
    durum INTEGER DEFAULT 0,
    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES users (id)
)
""")

# 3. YORUMLAR TABLOSU
# ... (Üstteki kodlar aynı) ...

# 4. MESAJLAR TABLOSU (YENİ)
cur.execute("""
CREATE TABLE mesajlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    isim TEXT NOT NULL,
    email TEXT NOT NULL,
    konu TEXT NOT NULL,
    mesaj TEXT NOT NULL,
    okundu INTEGER DEFAULT 0,
    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")


# --- KULLANICILARI OLUŞTUR ---

# 1. SEN (Admin)
admin_sifre = generate_password_hash("1234")
cur.execute("INSERT INTO users (ad_soyad, email, sifre, rol, biyografi) VALUES (?, ?, ?, ?, ?)",
            ('Ömer Faruk Bilgiç', 'admin@polletika.com', admin_sifre, 'admin', 'Prometheon Genel Yayın Yönetmeni. İktisat ve Veri üzerine çalışır.'))

# 2. AHMET ARİF ERDOĞAN (Yazar)
yazar_sifre = generate_password_hash("1234")
cur.execute("INSERT INTO users (ad_soyad, email, sifre, rol, biyografi) VALUES (?, ?, ?, ?, ?)",
            ('Ahmet Arif Erdoğan', 'ahmet@prometheon.com', yazar_sifre, 'yazar', 'Prometheon Yazarı. Edebiyat ve Siyaset tutkunu.'))

connection.commit()
connection.close()

print("✅ Veritabanı güncellendi! Biyografi sistemi eklendi.")
print("✅ Ömer Faruk (Admin) ve Ahmet Arif (Yazar) oluşturuldu.")