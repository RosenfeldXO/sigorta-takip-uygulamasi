import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- AYARLAR VE BAĞLANTI ---
st.set_page_config(page_title="Sigorta Takip Sistemi", page_icon="🛡️", layout="wide")

# Google Sheets Bağlantısı (Cache kullanarak hızlandırıyoruz)
@st.cache_resource
def baglanti_kur():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # Streamlit Secrets'dan bilgileri alıyoruz
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

try:
    client = baglanti_kur()
    sheet = client.open("SigortaTakipDB").sheet1  # Senin oluşturduğun tablo adı
except Exception as e:
    st.error(f"Veritabanı Bağlantı Hatası: {e}")
    st.stop()

# --- ARAYÜZ TASARIMI ---

st.title("🛡️ Sigorta Acentesi Yönetim Paneli")

# Sol Menü
menu = st.sidebar.selectbox("Menü", ["Gösterge Paneli", "Yeni Poliçe Ekle", "Tüm Kayıtlar"])

# Tüm Verileri Çek
data = sheet.get_all_records()
df = pd.DataFrame(data)

# --- 1. GÖSTERGE PANELİ ---
if menu == "Gösterge Paneli":
    st.subheader("📊 Genel Durum")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Toplam Müşteri", len(df))
    # Basit bir ciro hesabı (Tutar sütunu varsa)
    toplam_ciro = df['Tutar'].sum() if 'Tutar' in df.columns and not df.empty else 0
    col2.metric("Toplam Ciro", f"{toplam_ciro} ₺")
    
    st.info("💡 İPUCU: Veritabanında (Google Sheets) 1. Satıra şu başlıkları yazdığından emin ol: Ad Soyad, Telefon, Plaka, Sigorta Turu, Bitis Tarihi, Tutar")

# --- 2. YENİ POLİÇE EKLE ---
elif menu == "Yeni Poliçe Ekle":
    st.subheader("📝 Yeni Kayıt Girişi")
    
    with st.form("yeni_kayit_formu", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        ad = col_a.text_input("Adı Soyadı")
        tel = col_b.text_input("Telefon (5XX...)")
        plaka = col_a.text_input("Plaka")
        tur = col_b.selectbox("Sigorta Türü", ["Trafik", "Kasko", "DASK", "Konut", "Sağlık"])
        tarih = col_a.date_input("Bitiş Tarihi")
        tutar = col_b.number_input("Tutar (TL)", min_value=0)
        notlar = st.text_area("Notlar")
        
        submitted = st.form_submit_button("✅ Kaydet")
        
        if submitted:
            if ad == "":
                st.warning("Lütfen isim giriniz.")
            else:
                yeni_veri = [ad, tel, plaka, tur, str(tarih), tutar, notlar]
                sheet.append_row(yeni_veri)
                st.success(f"{ad} başarıyla sisteme eklendi!")
                
                # WhatsApp Linki Üret
                tel_temiz = tel.replace(" ", "")
                if not tel_temiz.startswith("90"):
                    tel_temiz = "90" + tel_temiz.lstrip("0")
                link = f"https://wa.me/{tel_temiz}?text=Sayın%20{ad.replace(' ', '%20')},%20sigorta%20poliçeniz%20oluşturulmuştur."
                st.markdown(f"[📲 Müşteriye WhatsApp Mesajı Gönder]({link})")

# --- 3. TÜM KAYITLAR ---
elif menu == "Tüm Kayıtlar":
    st.subheader("📂 Müşteri ve Poliçe Listesi")
    
    arama = st.text_input("🔍 İsim veya Plaka Ara")
    
    if not df.empty:
        gosterilecek_df = df
        if arama:
            gosterilecek_df = df[df.astype(str).apply(lambda x: x.str.contains(arama, case=False)).any(axis=1)]
        
        st.dataframe(gosterilecek_df, use_container_width=True)
    else:
        st.warning("Henüz hiç kayıt yok.")
