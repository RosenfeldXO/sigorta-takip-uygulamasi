import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import uuid
import urllib.parse
import re
import base64

# --- GÜVENLİK AYARLARI ---
TIMEOUT_DAKIKA = 30
TIMEOUT = timedelta(minutes=TIMEOUT_DAKIKA)
# --------------------------

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Sigorta Yönetim Paneli", page_icon="🛡️", layout="wide")

# --- GÜVENLİK DUVARI ---
def giris_kontrol():
    if 'giris_yapildi' not in st.session_state:
        st.session_state['giris_yapildi'] = False
        st.session_state['son_giris_zamani'] = datetime.min
        
    if st.session_state['giris_yapildi']:
        gecen_sure = datetime.now() - st.session_state['son_giris_zamani']
        if gecen_sure > TIMEOUT:
            st.session_state['giris_yapildi'] = False
            st.warning(f"⚠️ Oturum süresi doldu! {TIMEOUT_DAKIKA} dakika hareketsizlik nedeniyle lütfen yeniden şifre girin.")

    if not st.session_state['giris_yapildi']:
        st.header("🔒 Yönetici Girişi")
        sifre = st.text_input("Yönetici Şifresi", type="password")
        if st.button("Giriş Yap"):
            if sifre == st.secrets["admin_password"]:
                st.session_state['giris_yapildi'] = True
                st.session_state['son_giris_zamani'] = datetime.now() 
                st.rerun()
            else:
                st.error("Hatalı Şifre!")
        st.stop()
        
    st.session_state['son_giris_zamani'] = datetime.now()

giris_kontrol()

# --- BAĞLANTI ---
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
    try:
        tarih_obj = datetime.strptime(bitis_tarihi_str, "%Y-%m-%d")
        baslangic = tarih_obj.strftime("%Y%m%d")
        bitis = (tarih_obj + timedelta(days=1)).strftime("%Y%m%d")
        text = urllib.parse.quote(baslik)
        details = urllib.parse.quote(detay)
        url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={text}&dates={baslangic}/{bitis}&details={details}"
        return url
    except:
        return "#"

def tutar_temizle(deger):
    s = str(deger).strip()
    if not s or s in ["-", "--", "nan", "None", "null", "0"]:
        return 0.0
    if isinstance(deger, (int, float)):
        return float(deger)
    s = re.sub(r"[^0-9,.]", "", s)
    
    last_comma = s.rfind(',')
    last_dot = s.rfind('.')
    
    if last_comma > last_dot:
        s = s.replace('.', '').replace(',', '.')
    elif last_dot > last_comma:
        s = s.replace(',', '')
    elif last_comma != -1:
         s = s.replace(',', '.')
    elif last_dot != -1:
         s = s.replace('.', '')
    try:
        return float(s)
    except:
        return 0.0

def veri_hazirla(df):
    if not df.empty and 'Tutar' in df.columns:
        df['Tutar_Sayi'] = df['Tutar'].apply(tutar_temizle)
    return df

# --- HTML TEKLİF ŞABLONU OLUŞTURUCU (YENİ LİFE) ---
def teklif_html_uret(musteri, teklifler, acente_adi, acente_yetkili, logo_b64=None):
    logo_html = ""
    if logo_b64:
        # LOGO BOYUTU BÜYÜTÜLDÜ (250px)
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="max-height: 250px; margin-bottom: 20px; display: block; margin-left: auto; margin-right: auto;">'
    
    html = f"""
    <html>
    <head>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4; }}
        .container {{ background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); max-width: 800px; margin: auto; }}
        .header {{ text-align: center; border-bottom: 2px solid #004085; padding-bottom: 20px; margin-bottom: 20px; }}
        .header h1 {{ color: #004085; margin: 0; }}
        .header p {{ color: #666; }}
        .info {{ margin-bottom: 20px; font-size: 1.1em; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th {{ background-color: #004085; color: white; padding: 12px; text-align: left; }}
        td {{ border-bottom: 1px solid #ddd; padding: 12px; }}
        .fiyat {{ font-weight: bold; color: #28a745; font-size: 1.2em; }}
        .footer {{ margin-top: 30px; text-align: center; font-size: 0.9em; color: #777; border-top: 2px solid #004085; padding-top: 20px; margin-top: 30px; }}
    </style>
    </head>
    <body>
    <div class="container">
        <div class="header">
            {logo_html}
            <h1>SİGORTA TEKLİF SUNUMU</h1>
            <p>Size Özel Hazırlanan Karşılaştırmalı Teklifler</p>
        </div>
        <div class="info">
            <strong>Sayın:</strong> {musteri}<br>
            <strong>Tarih:</strong> {datetime.now().strftime('%d.%m.%Y')}
        </div>
        <table>
            <tr>
                <th>Firma</th>
                <th>Kapsam / Özellikler</th>
                <th>Fiyat</th>
            </tr>
    """
    
    for t in teklifler:
        try:
            fiyat_formatli = float(t['fiyat'])
        except ValueError:
            fiyat_formatli = 0.0
            
        html += f"""
            <tr>
                <td><strong>{t['firma']}</strong></td>
                <td>{t['ozellik']}</td>
                <td class="fiyat">{fiyat_formatli:,.2f} TL</td>
            </tr>
        """
        
    html += f"""
        </table>
        <div class="footer">
            <p>Bu teklif bilgilendirme amaçlıdır. Poliçe onayı için lütfen iletişime geçiniz.</p>
            <p><strong>{acente_adi}</strong></p>
            <p><strong>Yetkili: {acente_yetkili}</strong></p>
        </div>
    </div>
    </body>
    </html>
    """
    return html

# --- ARAYÜZ ---
st.sidebar.title("🛡️ Panel Menüsü")
st.sidebar.success("✅ Yönetici: Aktif")
menu = st.sidebar.radio("İşlemler", ["Yeni Poliçe Kes", "Kayıtları İncele", "Raporlar", "Teklif Sihirbazı 🪄"])

try:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df = veri_hazirla(df)
except:
    st.error(f"Veri yüklenemedi: Lütfen Google Sheets bağlantısını kontrol edin.")
    df = pd.DataFrame()


# --- 1. YENİ POLİÇE ---
if menu == "Yeni Poliçe Kes":
    st.header("📝 Yeni Poliçe Girişi")
    secilen_tur = st.selectbox("Sigorta Türü Seçiniz:", ["Trafik Sigortası", "Kasko", "DASK", "Konut", "Sağlık", "Seyahat"])
    arac_sigortasi_mi = secilen_tur in ["Trafik Sigortası", "Kasko"]
    st.markdown("---") 
    with st.form("police_formu"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("👤 Müşteri Bilgileri")
            ad = st.text_input("Ad Soyad / Ünvan")
            referans = st.text_input("Referans (Opsiyonel)")
            tc_no = st.text_input("T.C. / Vergi No")
            dogum_tarihi = st.date_input("Doğum Tarihi", min_value=datetime(1930, 1, 1), max_value=datetime.now())
            tel = st.text_input("Telefon (5XX...)")
        
        with col2:
            st.subheader("📄 Poliçe Detayları")
            sirket = st.selectbox("Sigorta Firması", ["Allianz", "Axa", "Anadolu", "Sompo", "Mapfre", "Türkiye Sigorta", "HDI", "Diğer"])
            baslangic = st.date_input("Başlangıç Tarihi")
            bitis = st.date_input("Bitiş Tarihi", value=baslangic + timedelta(days=365))
            tutar = st.number_input("Poliçe Tutarı (TL)", min_value=0.0, step=100.0)

        plaka, ruhsat, model = "-", "-", "-"
        if arac_sigortasi_mi:
            st.info(f"🚗 {secilen_tur} için Araç Bilgileri:")
            c_arac1, c_arac2 = st.columns(2)
            plaka = c_arac1.text_input("Plaka (Örn: 34ABC123)")
            ruhsat = c_arac2.text_input("Ruhsat Seri No")
            model = st.text_input("Araç Marka/Model ve Yılı (Örn: Toyota Corolla 2020)")
        
        notlar = st.text_area("Ek Notlar")
        oto_police_no = str(uuid.uuid4().hex[:8]).upper()
        
        submitted = st.form_submit_button("✅ Kaydı Tamamla")
        
        if submitted:
            hata_var = False
            if not ad:
                st.error("Müşteri Adı boş olamaz!")
                hata_var = True
            if arac_sigortasi_mi and (len(plaka) < 3 or not ruhsat):
                st.error("Trafik/Kasko için Plaka ve Ruhsat zorunludur!")
                hata_var = True
            
            if not hata_var:
                yeni_veri = [
                    oto_police_no, ad, referans, tc_no, 
                    str(dogum_tarihi),
                    tel, secilen_tur, sirket, plaka, ruhsat, 
                    model,
                    str(baslangic), str(bitis), tutar, notlar, "Hayır"
                ]
                sheet.append_row(yeni_veri)
                st.success("Kaydedildi!")

# --- 2. İNCELEME VE TAKVİM ---
elif menu == "Kayıtları İncele":
    st.header("📂 Kayıt Listesi ve Takvim Yönetimi")
    
    if df.empty:
        st.warning("Henüz kayıt yok.")
    else:
        arama = st.text_input("🔍 İsim, Plaka, TC veya Poliçe No Ara")
        goster_df = df.copy()
        
        if arama:
            goster_df = df[df.astype(str).apply(lambda x: x.str.contains(arama, case=False)).any(axis=1)]

        def renklendir_sutunlar(row):
            styles = [''] * len(row)
            
            if row[15] == "✅":
                styles[15] = 'background-color: #d4edda; color: black;'
            else:
                styles[15] = 'background-color: #f8d7da; color: black;'
                
            styles[11] = 'background-color: #d4edda; color: black;'
            styles[12] = 'background-color: #f8d7da; color: black;'
            
            return styles


        st.dataframe(
            goster_df.drop(columns=['Tutar_Sayi'], errors='ignore').style.apply(renklendir_sutunlar, axis=1),
            use_container_width=True
        )

        st.markdown("---")
        st.subheader("📅 Takvim İşlem Paneli")
        
        secenekler = goster_df.apply(lambda x: f"{x['PoliceNo']} - {x['Musteri']} ({x['Takvim_Durumu']})", axis=1)
        secilen_kayit_str = st.selectbox("İşlem Yapılacak Kaydı Seçin:", secenekler)
        
        if secilen_kayit_str:
            secilen_id = secilen_kayit_str.split(" - ")[0]
            kayit = df[df['PoliceNo'] == secilen_id].iloc[0]
            
            takvim_mesaji = f"📌 SİGORTA HATIRLATMASI\n------------------------\n" \
                            f"👤 Müşteri: {kayit['Musteri']}\n" \
                            f"🎂 D.Tarihi: {kayit['Dogum_Tarihi']}\n" \
                            f"📞 Tel: {kayit['Telefon']}\n" \
                            f"🆔 TC: {kayit['TC_Vergi_No']}\n" \
                            f"🛡️ Tür: {kayit['Sigorta_Turu']}\n" \
                            f"📄 No: {kayit['PoliceNo']}\n"
            
            if str(kayit['Plaka']) != "-" and len(str(kayit['Plaka'])) > 2:
                takvim_mesaji += f"------------------------\n🚗 Plaka: {kayit['Plaka']}\n🚙 Model: {kayit['Arac_Modeli']}\n"
            
            cal_url = google_takvim_linki_uret(f"BİTİŞ: {kayit['Musteri']}", str(kayit['Bitis_Tarihi']), takvim_mesaji)
            
            col_btn1, col_btn2 = st.columns(2)
            col_btn1.markdown(f"<a href='{cal_url}' target='_blank' style='display:block; background-color:#4285F4; color:white; padding:10px; text-align:center; border-radius:5px; text-decoration:none;'>📅 Takvime Ekle</a>", unsafe_allow_html=True)
            
            if col_btn2.button("✅ 'Eklendi' Olarak İşaretle"):
                try:
                    cell = sheet.find(secilen_id)
                    sheet.update_cell(cell.row, 16, "✅")
                    st.success("Güncellendi!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Hata: {e}")

# --- 3. RAPORLAR ---
elif menu == "Raporlar":
    st.header("📊 Patron Ekranı")
    
    if df.empty:
        st.warning("Veri yok.")
    else:
        ESIK_DEGER = 100000 
        hatali_df = df[df['Tutar_Sayi'] > ESIK_DEGER]
        gercek_ciro = df[df['Tutar_Sayi'] <= ESIK_DEGER]['Tutar_Sayi'].sum()
        
        col1, col2, col3 = st.columns(3)
        toplam_police = len(df)
        aktif_sirket_sayisi = df['Sigorta_Sirketi'].nunique()
        
        col1.metric("Poliçe Adedi", toplam_police)
        col2.metric("Firma Sayısı", aktif_sirket_sayisi)
        
        if not hatali_df.empty:
            col3.metric("Toplam Ciro", f"{gercek_ciro:,.2f} ₺", delta=f"⚠️ {len(hatali_df)} Hatalı Kayıt Hariç", delta_color="inverse")
            st.error(f"⚠️ DİKKAT! {len(hatali_df)} adet kayıtta anormal yüksek tutar tespit edildi. Cirolarınıza dahil edilmedi.")
            st.dataframe(hatali_df[['Musteri', 'Sigorta_Turu', 'Tutar', 'Tutar_Sayi']], use_container_width=True)
        else:
            col3.metric("Toplam Ciro", f"{gercek_ciro:,.2f} ₺")
            st.success("✅ Tüm veriler temiz görünüyor.")
            
        st.markdown("---")
        
        with st.expander("💰 Detaylı Finansal Rapor"):
            c1, c2 = st.columns(2)
            
            firma_ozeti = df.groupby('Sigorta_Sirketi')['Tutar_Sayi'].sum().sort_values(ascending=False).reset_index()
            firma_ozeti['Tutar_Sayi'] = firma_ozeti['Tutar_Sayi'].apply(lambda x: f"{x:,.2f} ₺")
            c1.dataframe(firma_ozeti, use_container_width=True)
            
            tur_ozeti = df.groupby('Sigorta_Turu')['Tutar_Sayi'].sum().sort_values(ascending=False).reset_index()
            tur_ozeti['Tutar_Sayi'] = tur_ozeti['Tutar_Sayi'].apply(lambda x: f"{x:,.2f} ₺")
            c2.dataframe(tur_ozeti, use_container_width=True)

        st.markdown("---")
        st.subheader("🔎 Veri Analizi")
        
        fc1, fc2 = st.columns(2)
        tum_firmalar = ["Tümü"] + list(df['Sigorta_Sirketi'].unique())
        tum_referanslar = ["Tümü"] + list(df[df['Referans'] != ""]['Referans'].unique())
        
        s_firma = fc1.selectbox("Firma:", tum_firmalar)
        s_ref = fc2.selectbox("Referans:", tum_referanslar)
        
        f_df = df.copy()
        if s_firma != "Tümü":
            f_df = f_df[f_df['Sigorta_Sirketi'] == s_firma]
        if s_ref != "Tümü":
            f_df = f_df[f_df['Referans'] == s_ref]
            
        st.write(f"Kayıt: {len(f_df)}")
        st.dataframe(f_df.drop(columns=['Tutar_Sayi'], errors='ignore'), use_container_width=True)


# --- 4. TEKLİF SİHİRBAZI 🪄 (GÜNCELLENDİ) ---
elif menu == "Teklif Sihirbazı 🪄":
    st.header("✨ Profesyonel Teklif Hazırla")
    st.info("Müşteriye sunmak istediğiniz teklifleri aşağıya girin.")

    # Oturumda offer_count yoksa, 3 ile başlat
    if 'offer_count' not in st.session_state:
        st.session_state['offer_count'] = 3
    
    # --- Acente Ayarları ve Logo Yükleyici ---
    st.subheader("⚙️ Acente Ayarları")
    col_logo, col_acente = st.columns([1, 2])
    
    with col_logo:
        if 'logo_b64' not in st.session_state: st.session_state['logo_b64'] = None

        uploaded_logo = st.file_uploader("Logo Yükle (PNG/JPG)", type=["png", "jpg", "jpeg"], key="logo_uploader")
        if uploaded_logo is not None:
            st.session_state['logo_b64'] = base64.b64encode(uploaded_logo.getvalue()).decode()
            st.success("Logo yüklendi!")
            st.image(uploaded_logo, caption="Yüklenen Logo", width=100)
        elif st.session_state['logo_b64']:
            st.image(f"data:image/png;base64,{st.session_state['logo_b64']}", caption="Mevcut Logo", width=100)

    with col_acente:
        acente_adi = st.text_input("Acente Adı:", value="Erikciler Sigorta", key="acente_adi")
        acente_yetkili = st.text_input("Acente Yetkilisi:", value="Sedat Ay", key="acente_yetkilisi")
    
    st.markdown("---")

    # Müşteri Bilgisi
    musteri_ad = st.text_input("Müşteri Ad Soyad:", placeholder="Örn: Ahmet Yılmaz", key="musteri_ad")

    st.markdown("---")
    
    # --- DİNAMİK TEKLİF GİRİŞİ ---
    st.subheader("📝 Teklif Girişleri")

    # + Butonuna basıldığında sayacı artır
    if st.button("+ Teklif Ekle", key="add_offer"):
        st.session_state['offer_count'] += 1
        st.rerun()

    teklifler = []
    
    # Teklifleri döngü ile oluştur
    for i in range(st.session_state['offer_count']):
        st.markdown(f"#### {i+1}. Teklif")
        cols = st.columns([1.5, 3, 1.5])
        
        with cols[0]:
            f = st.selectbox("Firma", ["Allianz", "Axa", "Anadolu", "Sompo", "Mapfre", "Türkiye Sigorta", "HDI", "Diğer"], key=f"f_{i}_sb", label_visibility="collapsed")
        
        with cols[1]:
            o = st.text_area("Özellikler (İMM, İkame...)", key=f"o_{i}_ta", height=50, label_visibility="collapsed", placeholder="Kapsam/Ek Özellikler")
        
        with cols[2]:
            p = st.text_input("Fiyat (TL)", key=f"p_{i}_ti", label_visibility="collapsed", placeholder="Fiyat (Sadece rakam)")
        
        if p and p.strip() != "": 
            teklifler.append({"firma": f, "ozellik": o, "fiyat": p})
        
        st.markdown("---")

    # --- SUNUM BUTONU VE ÇIKTI ---
    if st.button("🚀 Teklif Sunumu Oluştur", key="generate_final"):
        if not musteri_ad or not teklifler:
            st.error("Lütfen müşteri adı ve en az bir geçerli teklif giriniz.")
        else:
            # HTML Oluştur
            html_content = teklif_html_uret(
                musteri_ad, 
                teklifler, 
                acente_adi, 
                acente_yetkili, 
                st.session_state['logo_b64']
            )
            
            # Önizleme
            st.success("Teklif başarıyla oluşturuldu! Aşağıdan önizleyebilir ve indirebilirsiniz.")
            st.components.v1.html(html_content, height=500, scrolling=True)
            
            # İndirme Butonu (HTML'den PDF'e çevirme rehberliği ile)
            b64_html = base64.b64encode(html_content.encode()).decode()
            href = f'<a href="data:text/html;base64,{b64_html}" download="{musteri_ad}_Teklif.html" style="background-color:#28a745; color:white; padding:15px; text-decoration:none; border-radius:5px; font-weight:bold;">📥 HTML İndir (PDF Kaydetmek İçin)</a>'
            st.markdown(href, unsafe_allow_html=True)
            
            st.info("💡 PDF KAYIT TALİMATI: İndirdiğiniz HTML dosyasını açın ve tarayıcınızdan **Ctrl+P** (Mac'te Command+P) yaparak, açılan pencerede Hedef (Destination) olarak **'PDF Olarak Kaydet'**i seçin.")
