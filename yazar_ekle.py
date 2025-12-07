import sqlite3
from werkzeug.security import generate_password_hash

def yazar_ekle():
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    
    # Ahmet Arif Erdoğan'ı ekleyelim (Şifresi: 1234)
    ad = "Ahmet Arif Erdoğan"
    email = "ahmet@prometheon.com"
    sifre = generate_password_hash("1234")
    
    try:
        # Rolünü direkt 'yazar' yapıyoruz
        cur.execute("INSERT INTO users (ad_soyad, email, sifre, rol) VALUES (?, ?, ?, ?)", 
                    (ad, email, sifre, 'yazar'))
        conn.commit()
        print(f"✅ {ad} sisteme YAZAR olarak eklendi!")
    except sqlite3.IntegrityError:
        print(f"ℹ️ {ad} zaten sistemde kayıtlı.")
        
    conn.close()

if __name__ == "__main__":
    yazar_ekle()