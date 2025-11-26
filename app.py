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

# --- HTML TEKLİF ŞABLONU OLUŞTURUCU (YENİ) ---
def teklif_html_uret(musteri, teklifler):
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
        .footer {{ margin-top: 30px; text-align: center; font-size: 0.9em; color: #777; }}
    </style>
    </head>
    <body>
    <div class="container">
        <div class="header">
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
        html += f"""
            <tr>
                <td><strong>{t['firma']}</strong></td>
                <td>{t['ozellik']}</td>
                <td class="fiyat">{t['fiyat']} TL</td>
            </tr>
        """
        
    html += """
        </table>
        <div class="footer">
            <p>Bu teklif bilgilendirme amaçlıdır. Poliçe onayı için lütfen iletişime geçiniz.</p>
            <p><strong>Acenteniz Güvencesiyle</strong></p>
        </div>
    </div>
    </body>
    </html>
    """
    return html

# --- ARAYÜZ ---
st.sidebar.title("🛡️ Panel Menüsü")
st.sidebar.success("✅ Yönetici: Aktif")
# MENÜYE "TEKLİF SİHİRBAZI" EKLENDİ
menu = st.sidebar.radio("İşlemler", ["Yeni Poliçe Kes", "Kayıtları İncele", "Raporlar", "Teklif Sihirbazı 🪄"])

try:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df = veri_hazirla(df)
except:
    df = pd.DataFrame()

# --- 1. YENİ POLİÇE ---
if menu == "Yeni Poliçe Kes":
    st.header("📝 Yeni Poliçe Girişi")
    # ... (Eski kodlar aynı) ...
    secilen_tur = st.selectbox("Sigorta Türü Seçiniz:", ["Trafik Sigortası", "Kasko", "DASK", "Konut", "Sağlık", "Seyahat"])
    arac_sigortasi_mi = secilen_tur in ["Trafik Sigortası", "Kasko"]
    st.markdown("---") 
    with st.form("police_formu"):
        c1, c2 = st.columns(2)
        ad = c1.text_input("Ad Soyad")
        ref = c1.text_input("Referans")
        tc = c1.text_input("TC/Vergi No")
        dt = c1.date_input("Doğum Tarihi", min_value=datetime(1930,1,1))
        tel = c1.text_input("Telefon")
        sirket = c2.selectbox("Şirket", ["Allianz", "Axa", "Anadolu", "Sompo", "Mapfre", "Türkiye Sigorta", "HDI", "Diğer"])
        bas = c2.date_input("Başlangıç")
        bit = c2.date_input("Bitiş", value=bas+timedelta(days=365))
        tutar = c2.number_input("Tutar (TL)", step=100.0)
        plaka, ruhsat, model = "-", "-", "-"
        if arac_sigortasi_mi:
            cc1, cc2 = st.columns(2)
            plaka = cc1.text_input("Plaka")
            ruhsat = cc2.text_input("Ruhsat")
            model = st.text_input("Marka/Model")
        notlar = st.text_area("Not")
        oto_no = str(uuid.uuid4().hex[:8]).upper()
        if st.form_submit_button("✅ Kaydı Tamamla"):
             yeni = [oto_no, ad, ref, tc, str(dt), tel, secilen_tur, sirket, plaka, ruhsat, model, str(bas), str(bit), tutar, notlar, "Hayır"]
             sheet.append_row(yeni)
             st.success("Kaydedildi!")

# --- 2. İNCELEME ---
elif menu == "Kayıtları İncele":
    st.header("📂 Kayıt Listesi")
    # ... (Eski kodlar aynı, sadece sıkıştırma yapıldı) ...
    arama = st.text_input("🔍 Ara")
    g_df = df.copy()
    if arama:
        g_df = df[df.astype(str).apply(lambda x: x.str.contains(arama, case=False)).any(axis=1)]
    
    def renklendir(row):
        styles = [''] * len(row)
        styles[15] = 'background-color: #d4edda; color: black;' if row[15] == "✅" else 'background-color: #f8d7da; color: black;'
        styles[11] = 'background-color: #d4edda; color: black;'
        styles[12] = 'background-color: #f8d7da; color: black;'
        return styles

    st.dataframe(g_df.drop(columns=['Tutar_Sayi'], errors='ignore').style.apply(renklendir, axis=1), use_container_width=True)
    
    sec = st.selectbox("İşlem Yap", g_df.apply(lambda x: f"{x['PoliceNo']} - {x['Musteri']}", axis=1))
    if sec:
        sid = sec.split(" - ")[0]
        k = df[df['PoliceNo'] == sid].iloc[0]
        # Link üretme vs... (Aynı mantık)
        msg = f"SİGORTA: {k['Musteri']} - {k['Plaka']}"
        lnk = google_takvim_linki_uret(f"BİTİŞ: {k['Musteri']}", str(k['Bitis_Tarihi']), msg)
        c1, c2 = st.columns(2)
        c1.markdown(f"<a href='{lnk}' target='_blank'>📅 Takvim Linki</a>", unsafe_allow_html=True)
        if c2.button("✅ Eklendi Yap"):
            cell = sheet.find(sid)
            sheet.update_cell(cell.row, 16, "✅")
            st.rerun()

# --- 3. RAPORLAR ---
elif menu == "Raporlar":
    st.header("📊 Patron Ekranı")
    # ... (Eski rapor kodları) ...
    ESIK = 100000
    temiz_ciro = df[df['Tutar_Sayi'] <= ESIK]['Tutar_Sayi'].sum()
    hatali = df[df['Tutar_Sayi'] > ESIK]
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Poliçe", len(df))
    c2.metric("Firma", df['Sigorta_Sirketi'].nunique())
    if not hatali.empty:
        c3.metric("Ciro", f"{temiz_ciro:,.2f} ₺", "Hatalı Veri Var", delta_color="inverse")
        st.error("Hatalı yüksek tutarlar toplama dahil edilmedi.")
    else:
        c3.metric("Ciro", f"{temiz_ciro:,.2f} ₺")
        
    st.dataframe(df.drop(columns=['Tutar_Sayi'], errors='ignore'), use_container_width=True)


# --- 4. YENİ BÖLÜM: TEKLİF SİHİRBAZI 🪄 ---
elif menu == "Teklif Sihirbazı 🪄":
    st.header("✨ Profesyonel Teklif Hazırla")
    st.info("Müşteriye sunmak istediğiniz teklifleri aşağıya girin. Sistem otomatik bir sunum dosyası hazırlayacaktır.")

    # Müşteri Bilgisi
    musteri_ad = st.text_input("Müşteri Ad Soyad:", placeholder="Örn: Ahmet Yılmaz")

    st.markdown("---")
    
    # 3 Teklif Girişi için Kolonlar
    col1, col2, col3 = st.columns(3)
    
    teklifler = []

    # 1. Teklif
    with col1:
        st.subheader("1. Seçenek")
        f1 = st.selectbox("Firma 1", ["Allianz", "Axa", "Anadolu", "Sompo", "Mapfre", "Diğer"], key="f1")
        o1 = st.text_area("Özellikler (İMM, İkame...)", key="o1", height=100)
        p1 = st.text_input("Fiyat 1 (TL)", key="p1")
        if p1: teklifler.append({"firma": f1, "ozellik": o1, "fiyat": p1})

    # 2. Teklif
    with col2:
        st.subheader("2. Seçenek")
        f2 = st.selectbox("Firma 2", ["Axa", "Allianz", "Anadolu", "Sompo", "Mapfre", "Diğer"], key="f2")
        o2 = st.text_area("Özellikler", key="o2", height=100)
        p2 = st.text_input("Fiyat 2 (TL)", key="p2")
        if p2: teklifler.append({"firma": f2, "ozellik": o2, "fiyat": p2})

    # 3. Teklif (Opsiyonel)
    with col3:
        st.subheader("3. Seçenek (Opsiyonel)")
        f3 = st.selectbox("Firma 3", ["Sompo", "Allianz", "Axa", "Anadolu", "Mapfre", "Diğer"], key="f3")
        o3 = st.text_area("Özellikler", key="o3", height=100)
        p3 = st.text_input("Fiyat 3 (TL)", key="p3")
        if p3: teklifler.append({"firma": f3, "ozellik": o3, "fiyat": p3})

    st.markdown("---")

    if st.button("🚀 Teklif Sunumu Oluştur"):
        if not musteri_ad or not teklifler:
            st.error("Lütfen müşteri adı ve en az bir teklif giriniz.")
        else:
            # HTML Oluştur
            html_content = teklif_html_uret(musteri_ad, teklifler)
            
            # Önizleme
            st.success("Teklif başarıyla oluşturuldu! Aşağıdan önizleyebilir veya indirebilirsiniz.")
            st.components.v1.html(html_content, height=500, scrolling=True)
            
            # İndirme Butonu
            b64 = base64.b64encode(html_content.encode()).decode()
            href = f'<a href="data:file/html;base64,{b64}" download="{musteri_ad}_Teklif.html" style="background-color:#28a745; color:white; padding:15px; text-decoration:none; border-radius:5px; font-weight:bold;">📥 Teklifi İndir (WhatsApp İçin)</a>'
            st.markdown(href, unsafe_allow_html=True)
            
            st.info("💡 İPUCU: İndirdiğiniz dosyayı telefonda açıp 'Ekran Görüntüsü' alarak WhatsApp'tan atabilirsiniz.")
