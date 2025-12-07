import sqlite3

def sutun_ekle():
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # 'goruntulenme' sütununu ekle (Varsayılan değer 0)
        cursor.execute("ALTER TABLE yazilar ADD COLUMN goruntulenme INTEGER DEFAULT 0")
        
        conn.commit()
        conn.close()
        print("✅ Başarılı: 'goruntulenme' sütunu eklendi!")
    except sqlite3.OperationalError:
        print("⚠️ Bilgi: Bu sütun zaten var, işlem yapılmadı.")
    except Exception as e:
        print(f"❌ Bir hata oluştu: {e}")

if __name__ == "__main__":
    sutun_ekle()