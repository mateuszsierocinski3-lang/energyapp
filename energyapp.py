import streamlit as st
import pandas as pd
import requests
import time
import io
import zipfile

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="EPREL Data & PDF Downloader", page_icon="⚡", layout="wide")

def get_eprel_data(eprel_id, ean, api_key):
    """Pobiera dane produktu (JSON) z API EPREL."""
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    
    # 1. Próba po ID EPREL
    if eprel_id and str(eprel_id).lower() != 'nan' and str(eprel_id).strip() != "":
        url = f"https://eprel.ec.europa.eu/api/product/{str(eprel_id).strip()}"
    # 2. Próba po GTIN (EAN)
    elif ean and str(ean).lower() != 'nan' and str(ean).strip() != "":
        clean_ean = str(ean).split('.')[0].strip()
        url = f"https://eprel.ec.europa.eu/api/product/gtin/{clean_ean}"
    else:
        return None
        
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return data[0] if isinstance(data, list) else data
    except:
        return None
    return None

def download_pdf(url, api_key):
    """Pobiera surową zawartość pliku PDF z API."""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            return res.content
    except:
        return None
    return None

# --- UI ---
st.title("⚡ EPREL PDF Downloader & Scraper")
st.markdown("Pobiera klasę energetyczną oraz pliki PDF (Etykiety i Karty) do paczki ZIP.")

try:
    # Pobranie klucza z Streamlit Cloud Secrets
    API_KEY = st.secrets["EPREL_API_KEY"]
except:
    st.error("Błąd: Nie znaleziono 'EPREL_API_KEY' w Secrets aplikacji!")
    st.stop()

uploaded_file = st.file_uploader("Wgraj plik Excel (kolumny: 'ean' i 'kod eprel')", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    cols = {c.lower(): c for c in df_in.columns}
    
    if 'ean' not in cols or 'kod eprel' not in cols:
        st.error("Plik musi zawierać kolumny: 'ean' i 'kod eprel'!")
    else:
        if st.button("Uruchom pobieranie danych i plików PDF"):
            results = []
            pdf_files = [] # Lista krotek (nazwa_pliku, zawartość_binarna)
            
            progress = st.progress(0)
            status_text = st.empty()
            
            ean_col = cols['ean']
            code_col = cols['kod eprel']

            for i, row in df_in.iterrows():
                e_id = row[code_col]
                e_ean = str(row[ean_col]).split('.')[0].strip()
                
                status_text.text(f"Przetwarzanie ({i+1}/{len(df_in)}): EAN {e_ean}")
                
                data = get_eprel_data(e_id, e_ean, API_KEY)
                
                entry = {
                    "EAN": e_ean,
                    "EPREL_ID": "Nie znaleziono",
                    "Klasa": "N/A",
                    "Status_PDF": "Brak"
                }
                
                if data:
                    reg_num = data.get('registrationNumber')
                    entry["EPREL_ID"] = reg_num
                    entry["Klasa"] = data.get('energyClass', 'N/A')
                    
                    # Definiowanie linków do plików
                    fiche_url = f"https://eprel.ec.europa.eu/api/product/{reg_num}/fiches?format=PDF&language=PL"
                    label_url = f"https://eprel.ec.europa.eu/api/product/{reg_num}/label?format=PDF"
                    
                    # Pobieranie ETYKIETY
                    label_content = download_pdf(label_url, API_KEY)
                    if label_content:
                        pdf_files.append((f"ETYKIETA_{e_ean}_{reg_num}.pdf", label_content))
                    
                    # Pobieranie KARTY PRODUKTU
                    fiche_content = download_pdf(fiche_url, API_KEY)
                    if fiche_content:
                        pdf_files.append((f"KARTA_{e_ean}_{reg_num}.pdf", fiche_content))
                    
                    entry["Status_PDF"] = "Pobrano" if label_content or fiche_content else "Błąd PDF"
                
                results.append(entry)
                progress.progress((i + 1) / len(df_in))
                time.sleep(0.1) # Ochrona przed rate-limitingiem API

            st.session_state.results_df = pd.DataFrame(results)
            status_text.success("Zakończono pobieranie!")

            # Tworzenie archiwum ZIP w pamięci
            if pdf_files:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for filename, content in pdf_files:
                        zip_file.writestr(filename, content)
                st.session_state.zip_data = zip_buffer.getvalue()

# --- SEKCJA POBIERANIA WYNIKÓW ---
if 'results_df' in st.session_state:
    st.divider()
    st.subheader("Wyniki operacji")
    st.dataframe(st.session_state.results_df)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Excel
        out_buf = io.BytesIO()
        with pd.ExcelWriter(out_buf, engine='xlsxwriter') as writer:
            st.session_state.results_df.to_excel(writer, index=False)
        st.download_button(
            label="📥 Pobierz Raport Excel",
            data=out_buf.getvalue(),
            file_name="wyniki_eprel.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with col2:
        # ZIP
        if 'zip_data' in st.session_state:
            st.download_button(
                label="📂 Pobierz Paczkę PDF (ZIP)",
                data=st.session_state.zip_data,
                file_name="pliki_eprel.zip",
                mime="application/zip"
            )
