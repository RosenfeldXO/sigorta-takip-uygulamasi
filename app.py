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
    # Session state içinde giriş yapılıp yapılmadığını tutuyoruz
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
        st.stop() # Giriş yapılmadıysa kodun geri kalanını çalıştırma

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
def google_takvim_linki_uret(baslik, bitis_tarihi_str):
    """
    Google Takvim için özel link üretir.
    Hatırlatma notu ekler.
    """
    # Tarihi formatla
    tarih_obj = datetime.strptime(bitis_tarihi_str, "%Y-%m-%d")
    
    # Bitiş günü tüm gün etkinlik
    baslangic = tarih_obj.strftime("%Y%m%d")
    bitis = (tarih_obj + timedelta(days=1)).strftime("%Y%m%d")
    
    detay = "DİKKAT: Bu poliçenin süresi doluyor! Müşteriyi aramayı unutma."
    
    # Link oluşturma (URL Encoding)
    text = urllib.parse.quote(baslik)
    details = urllib.parse.quote(detay)
    url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={text}&dates={baslangic}/{bitis}&details={details}"
    return url

# --- ARAYÜZ ---
st.sidebar.title("🛡️ Panel Menüsü")
st.sidebar.success("✅ Yönetici: Aktif")
menu = st.sidebar.radio("İşlemler", ["Yeni Poliçe Kes", "Kayıtları İncele", "Raporlar"])

# Tüm veriyi çek
try:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
except:
    df = pd.DataFrame()

# --- 1. YENİ POLİÇE EKRANI ---
if menu == "Yeni Poliçe Kes":
    st.header("📝 Yeni Poliçe Girişi")
    
    with st.form("police_formu", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        # Müşteri Bilgileri
        ad = col1.text_input("Müşteri Ad Soyad")
        tel = col2.text_input("Telefon (Başında 0 olmadan)", placeholder="5XX...")
        
        # Sigorta Bilgileri
        tur = col1.selectbox("Sigorta Türü", ["Trafik Sigortası", "Kasko", "DASK", "Konut", "Sağlık"])
        
        # DİNAMİK ALAN MANTIĞI
        # Form içinde anlık değişim için session state kullanılabilir ama 
        # Streamlit formlarında en temizi koşullu göstermektir.
        # Ancak form içinde UI yenilenmediği için plaka alanını dışarıda soruyoruz ya da
        # Form mantığı gereği her zaman gösterip opsiyonel yapıyoruz. 
        # Fakat senin isteğin üzerine "Trafik veya Kasko değilse Plaka girilemesin" mantığını
        # formun dışında, veriyi kaydederken işleyeceğiz veya UI'da ipucu vereceğiz.
        
        plaka = col2.text_input("Plaka (Sadece Araç Sigortaları İçin)", help="DASK için boş bırakın")
        
        # Tarih ve Tutar
        tarih = col1.date_input("Poliçe Bitiş Tarihi")
        tutar = col2.number_input("Tutar (TL)", min_value=0)
        
        # Otomatik Poliçe No (Kullanıcı değiştiremez)
        oto_police_no = str(uuid.uuid4().hex[:8]).upper()
        st.info(f"Sistem tarafından atanacak Poliçe No: {oto_police_no}")
        
        submitted = st.form_submit_button("✅ Kaydı Tamamla")
        
        if submitted:
            # VALIDASYONLAR (Kurallar)
            hata_var = False
            
            if not ad:
                st.error("İsim boş olamaz!")
                hata_var = True
            
            # Plaka Kontrolü
            if tur in ["Trafik Sigortası", "Kasko"] and len(plaka) < 3:
                st.error("Trafik ve Kasko için Plaka girmek zorunludur!")
                hata_var = True
            
            # DASK ise Plakayı Temizle
            if tur == "DASK":
                plaka = "-"
                
            if not hata_var:
                # Veriyi Hazırla
                yeni_veri = [
                    oto_police_no, # Otomatik No
                    ad, 
                    tel, 
                    plaka, 
                    tur, 
                    str(tarih), 
                    tutar
                ]
                
                # Google Sheets'e Ekle
                sheet.append_row(yeni_veri)
                
                st.success(f"Kayıt Başarılı! Poliçe No: {oto_police_no}")
                
                # --- AKSİYON BUTONLARI ---
                c1, c2 = st.columns(2)
                
                # 1. WhatsApp Linki
                if tel:
                    tel_clean = "90" + tel.replace(" ", "").lstrip("0")
                    msg = f"Sayın {ad}, {tur} poliçeniz {oto_police_no} numarası ile oluşturulmuştur."
                    wa_url = f"https://wa.me/{tel_clean}?text={urllib.parse.quote(msg)}"
                    c1.markdown(f"[📲 WhatsApp Mesajı Gönder]({wa_url})", unsafe_allow_html=True)
                
                # 2. Google Takvim Linki (Bitiş Tarihi İçin)
                cal_title = f"BİTİŞ: {ad} - {tur}"
                cal_url = google_takvim_linki_uret(cal_title, str(tarih))
                
                c2.markdown(f"""
                <a href="{cal_url}" target="_blank" style="background-color:#4285F4; color:white; padding:8px 12px; text-decoration:none; border-radius:5px;">
                📅 Takvime Hatırlatıcı Ekle
                </a>
                """, unsafe_allow_html=True)
                st.info("👆 Takvim butonuna basınca açılan ekranda 'Bildirim' kısmını '2 Hafta Önce' olarak seçmeyi unutmayın.")

# --- 2. KAYITLARI İNCELE ---
elif menu == "Kayıtları İncele":
    st.header("📂 Veritabanı")
    arama = st.text_input("🔍 İsim, Plaka veya Poliçe No Ara")
    
    if not df.empty:
        # Önce veriyi gösterelim
        goster_df = df
        if arama:
            goster_df = df[df.astype(str).apply(lambda x: x.str.contains(arama, case=False)).any(axis=1)]
        st.dataframe(goster_df, use_container_width=True)
    else:
        st.warning("Henüz hiç kayıt yok.")

# --- 3. RAPORLAR ---
elif menu == "Raporlar":
    st.header("📊 Durum Özeti")
    if not df.empty:
        col1, col2 = st.columns(2)
        col1.metric("Toplam Poliçe", len(df))
        
        # Ciro Hesabı (Hata önleyici ile)
        try:
            # Tutar sütununun adını kontrol etmemiz lazım, 7. sütun olduğunu varsayıyoruz
            # Google Sheets'ten gelen veri string olabilir, temizliyoruz
            df['Tutar'] = pd.to_numeric(df.iloc[:, 6], errors='coerce').fillna(0) 
            toplam_ciro = df['Tutar'].sum()
            col2.metric("Toplam Ciro", f"{toplam_ciro:,.2f} ₺")
        except:
            col2.warning("Tutar hesaplanamadı, sütun başlıklarını kontrol et.")
            
        st.subheader("Türlere Göre Dağılım")
        st.bar_chart(df.iloc[:, 4].value_counts()) # 5. Sütun (Tür)
    else:
        st.info("Veri yok.")
