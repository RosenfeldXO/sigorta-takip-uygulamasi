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
    """
    Google Takvim linki üretir. Detay kısmındaki \n (yeni satır) karakterlerini
    web uyumlu hale getirir.
    """
    tarih_obj = datetime.strptime(bitis_tarihi_str, "%Y-%m-%d")
    baslangic = tarih_obj.strftime("%Y%m%d")
    bitis = (tarih_obj + timedelta(days=1)).strftime("%Y%m%d")
    
    text = urllib.parse.quote(baslik)
    details = urllib.parse.quote(detay) # Detayları URL formatına çevir
    
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

    # Sigorta Türü Seçimi
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
            referans = st.text_input("Referans (Opsiyonel)")
            tc_no = st.text_input("T.C. / Vergi No")
            tel = st.text_input("Telefon (5XX...)", max_chars=10)
        
        with col2:
            st.subheader("📄 Poliçe Detayları")
            sirket = st.selectbox("Sigorta Firması", ["Allianz", "Axa", "Anadolu", "Sompo", "Mapfre", "Türkiye Sigorta", "HDI", "Diğer"])
            baslangic = st.date_input("Başlangıç Tarihi")
            bitis = st.date_input("Bitiş Tarihi", value=baslangic + timedelta(days=365))
            tutar = st.number_input("Poliçe Tutarı (TL)", min_value=0.0, step=100.0)

        # --- ARAÇ BİLGİLERİ ---
        plaka, ruhsat, model, yil = "-", "-", "-", "-"
        
        if arac_sigortasi_mi:
            st.info(f"🚗 {secilen_tur} için Araç Bilgileri:")
            c_arac1, c_arac2 = st.columns(2)
            plaka = c_arac1.text_input("Plaka (Örn: 34ABC123)")
            ruhsat = c_arac2.text_input("Ruhsat Seri No")
            model = c_arac1.text_input("Araç Marka/Model")
            yil = c_arac2.number_input("Araç Yılı", min_value=1950, max_value=2030, step=1, value=2020)
        
        notlar = st.text_area("Ek Notlar")
        
        oto_police_no = str(uuid.uuid4().hex[:8]).upper()
        
        submitted = st.form_submit_button("✅ Kaydı Tamamla ve Gönder")
        
        if submitted:
            # Validasyon
            hata_var = False
            if not ad:
                st.error("Müşteri Adı boş olamaz!")
                hata_var = True
            if arac_sigortasi_mi and (len(plaka) < 3 or not ruhsat):
                st.error("Trafik/Kasko için Plaka ve Ruhsat zorunludur!")
                hata_var = True
            
            if not hata_var:
                # Veri Kaydı
                yeni_veri = [
                    oto_police_no, ad, referans, tc_no, tel,
                    secilen_tur, sirket, plaka, ruhsat, model,
                    str(yil), str(baslangic), str(bitis), tutar, notlar
                ]
                sheet.append_row(yeni_veri)
                st.success(f"✅ Kayıt Başarılı! Poliçe No: {oto_police_no}")
                
                # --- TAKVİM MESAJINI HAZIRLAMA (ÖZEL FORMAT) ---
                
                # Standart Mesaj
                takvim_mesaji = f"📌 SİGORTA HATIRLATMASI\n" \
                                f"------------------------\n" \
                                f"👤 Müşteri: {ad}\n" \
                                f"📞 Telefon: {tel}\n" \
                                f"🆔 T.C. No: {tc_no}\n" \
                                f"🛡️ Sigorta Türü: {secilen_tur}\n" \
                                f"📄 Poliçe No: {oto_police_no}\n" \
                                f"🏢 Şirket: {sirket}\n"

                # Araç ise ekstra bilgileri ekle
                if arac_sigortasi_mi:
                    takvim_mesaji += f"------------------------\n" \
                                     f"🚗 ARAÇ BİLGİLERİ:\n" \
                                     f"🚘 Plaka: {plaka}\n" \
                                     f"📜 Ruhsat: {ruhsat}\n" \
                                     f"🚙 Model: {model} ({yil})\n"
                
                if referans:
                    takvim_mesaji += f"🤝 Referans: {referans}"

                # Linkleri Oluştur
                c1, c2 = st.columns(2)
                
                # WhatsApp Linki
                if tel:
                    tel_clean = "90" + tel.replace(" ", "").lstrip("0")
                    msg = f"Sayın {ad}, {sirket} poliçeniz (No:{oto_police_no}) oluşturulmuştur."
                    wa_url = f"https://wa.me/{tel_clean}?text={urllib.parse.quote(msg)}"
                    c1.markdown(f"[📲 WhatsApp Mesajı]({wa_url})", unsafe_allow_html=True)
                
                # Takvim Linki (Yeni Mesaj İle)
                cal_url = google_takvim_linki_uret(f"BİTİŞ: {ad} - {plaka}", str(bitis), takvim_mesaji)
                c2.markdown(f"[📅 Takvime Hatırlatıcı Ekle]({cal_url})", unsafe_allow_html=True)

# --- 2. LİSTELEME EKRANI ---
elif menu == "Kayıtları İncele":
    st.header("📂 Kayıt Listesi")
    arama = st.text_input("🔍 İsim, Plaka, Referans veya TC Ara")
    
    if not df.empty:
        goster_df = df
        if arama:
            goster_df = df[df.astype(str).apply(lambda x: x.str.contains(arama, case=False)).any(axis=1)]
        st.dataframe(goster_df, use_container_width=True)
    else:
        st.info("Kayıt bulunamadı.")

# --- 3. RAPORLAR ---
elif menu == "Raporlar":
    st.header("📊 Performans Raporu")
    if not df.empty:
        col1, col2 = st.columns(2)
        col1.metric("Toplam Poliçe", len(df))
        
        if 'Tutar' in df.columns:
            df['Tutar_Sayi'] = pd.to_numeric(df['Tutar'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            col2.metric("Toplam Hacim", f"{df['Tutar_Sayi'].sum():,.2f} ₺")
        
        st.bar_chart(df['Sigorta_Sirketi'].value_counts())
