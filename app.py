import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import uuid
import urllib.parse

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Sigorta Yönetim Paneli", page_icon="🛡️", layout="wide")

# --- GÜVENLİK DUVARI (LOGIN) ---
def giris_kontrol():
    if 'giris_yapildi' not in st.session_state:
        st.session_state['giris_yapildi'] = False

    if not st.session_state['giris_yapildi']:
        st.header("🔒 Yönetici Girişi")
        sifre = st.text_input("Yönetici Şifresi", type="password")
        if st.button("Giriş Yap"):
            if sifre == st.secrets["admin_password"]:
                st.session_state['giris_yapildi'] = True
                st.rerun()
            else:
                st.error("Hatalı Şifre!")
        st.stop()

giris_kontrol()

# --- VERİTABANI BAĞLANTISI ---
@st.cache_resource
def baglanti_kur():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

try:
    client = baglanti_kur()
    sheet = client.open("SigortaTakipDB").sheet1
except Exception as e:
    st.error(f"Veritabanı Hatası: {e}")
    st.stop()

# --- YARDIMCI FONKSİYONLAR ---
def google_takvim_linki_uret(baslik, bitis_tarihi_str, detay):
    tarih_obj = datetime.strptime(bitis_tarihi_str, "%Y-%m-%d")
    baslangic = tarih_obj.strftime("%Y%m%d")
    bitis = (tarih_obj + timedelta(days=1)).strftime("%Y%m%d")
    text = urllib.parse.quote(baslik)
    details = urllib.parse.quote(detay)
    url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={text}&dates={baslangic}/{bitis}&details={details}"
    return url

# --- ARAYÜZ ---
st.sidebar.title("🛡️ Panel Menüsü")
st.sidebar.success("✅ Yönetici: Aktif")
menu = st.sidebar.radio("İşlemler", ["Yeni Poliçe Kes", "Kayıtları İncele", "Raporlar"])

# Verileri Çek
try:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
except:
    df = pd.DataFrame()

# --- 1. YENİ POLİÇE EKRANI ---
if menu == "Yeni Poliçe Kes":
    st.header("📝 Yeni Poliçe Girişi")

    # Sigorta Türü Seçimi (Form Dışı)
    secilen_tur = st.selectbox("Sigorta Türü Seçiniz:", 
                               ["Trafik Sigortası", "Kasko", "DASK", "Konut", "Sağlık", "Seyahat"])
    
    arac_sigortasi_mi = secilen_tur in ["Trafik Sigortası", "Kasko"]

    st.markdown("---") 

    with st.form("police_formu", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        # --- GENEL BİLGİLER ---
        with col1:
            st.subheader("👤 Müşteri Bilgileri")
            ad = st.text_input("Ad Soyad / Ünvan")
            referans = st.text_input("Referans (Kim Yönlendirdi?)", placeholder="Örn: Ahmet Bey / Sahibinden") # YENİ ALAN
            tc_no = st.text_input("T.C. / Vergi No")
            tel = st.text_input("Telefon (5XX...)", max_chars=10)
        
        with col2:
            st.subheader("📄 Poliçe Detayları")
            sirket = st.selectbox("Sigorta Firması", ["Allianz", "Axa", "Anadolu", "Sompo", "Mapfre", "Türkiye Sigorta", "HDI", "Diğer"])
            baslangic = st.date_input("Başlangıç Tarihi")
            bitis = st.date_input("Bitiş Tarihi", value=baslangic + timedelta(days=365))
            tutar = st.number_input("Poliçe Tutarı (TL)", min_value=0.0, step=100.0)

        # --- ARAÇ BİLGİLERİ (KOŞULLU) ---
        plaka, ruhsat, model, yil = "-", "-", "-", "-"
        
        if arac_sigortasi_mi:
            st
