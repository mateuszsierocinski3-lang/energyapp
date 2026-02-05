import streamlit as st
import pandas as pd
import requests
import time
import io
import zipfile

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="EPREL Downloader & Archiver", page_icon="⚡", layout="wide")

# --- FUNKCJE POMOCNICZE ---

def get_eprel_data(eprel_id, ean, api_key):
    """Pobiera dane produktu z API EPREL."""
    if eprel_id and str(eprel_id).lower() != 'nan' and str(eprel_id).strip() != "":
        url = f"https://eprel.ec.europa.eu/api/product/{eprel_id.strip()}"
    elif ean and str(ean).lower() != 'nan' and str(ean).strip() != "":
        url = f"https://eprel.ec.europa.eu/api/product/gtin/{ean.strip()}"
    else:
        return None

    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        return response.json() if response.status_code == 200 else None
    except:
        return None

def download_file(url, api_key):
    """Pobiera zawartość binarną pliku z API."""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        return resp.content if resp.status_code == 200 else None
    except:
        return None

# --- UI STREAMLIT ---
st.title("⚡ EPREL Pro: Dane + Załączniki ZIP")
st.info("Skrypt pobierze dane do Excela oraz pliki PNG/PDF nazwane Twoim numerem EAN.")

# Pobieranie klucza z Secrets
try:
    API_KEY = st.secrets["EPREL_API_KEY"]
except Exception:
    st.error("Błąd: Nie znaleziono klucza 'EPREL_API_KEY' w Streamlit Secrets!")
    st.stop()

uploaded_file = st.file_uploader("Załaduj plik Excel ('ean', 'kod eprel')", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    cols = [str(c).lower() for c in df_in.columns]
    
    if 'ean' not in cols or 'kod eprel' not in cols:
        st.error("Plik musi zawierać kolumny: 'ean' i 'kod eprel'")
    else:
        if st.button("Uruchom pobieranie danych i plików"):
            final_data = []
            zip_buffer = io.BytesIO()
            progress_bar = st.progress(0)
            
            ean_col = [c for c in df_in.columns if c.lower() == 'ean'][0]
            code_col = [c for c in df_in.columns if c.lower() == 'kod eprel'][0]

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for i, row in df_in.iterrows():
                    ean_val = str(row[ean_col]).split('.')[0].strip() if pd.notnull(row[ean_col]) else f"no_ean_{i}"
                    eprel_id_val = str(row[code_col]).split('.')[0].strip() if pd.notnull(row[code_col]) else ""
                    
                    entry = {"EAN": ean_val, "Klasa Energetyczna": "Nie znaleziono", "Status plików": "Brak"}
                    
                    data = get_eprel_data(eprel_id_val, ean_val, API_KEY)
                    
                    if data:
                        real_id = data.get("registrationNumber") or eprel_id_val
                        entry["Klasa Energetyczna"] = data.get("energyClass", "N/A")
                        
                        # Pobieranie Etykiety (PNG)
                        label_url = f"https://eprel.ec.europa.eu/api/product/{real_id}/label?format=PNG"
                        img_content = download_file(label_url, API_KEY)
                        if img_content:
                            zip_file.writestr(f"etykiety/{ean_val}.png", img_content)
                        
                        # Pobieranie Karty (PDF)
                        fiche_url = f"https://eprel.ec.europa.eu/api/product/{real_id}/fiches"
                        pdf_content = download_file(fiche_url, API_KEY)
                        if pdf_content:
                            zip_file.writestr(f"karty/{ean_val}.pdf", pdf_content)
                        
                        entry["Status plików"] = "Pobrano PNG i PDF"
                    
                    final_data.append(entry)
                    progress_bar.progress((i + 1) / len(df_in))
                    time.sleep(0.1)

            st.session_state.results_df = pd.DataFrame(final_data)
            st.session_state.zip_data = zip_buffer.getvalue()
            st.success("Przetwarzanie zakończone!")

# --- SEKCJA POBIERANIA ---
if 'results_df' in st.session_state:
    st.subheader("Wyniki operacji")
    st.dataframe(st.session_state.results_df)
    
    col1, col2 = st.columns(2)
    
    with col1:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            st.session_state.results_df.to_excel(writer, index=False)
        st.download_button(
            label="📥 Pobierz raport Excel",
            data=buf.getvalue(),
            file_name="eprel_klasy_energetyczne.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    with col2:
        st.download_button(
            label="📦 Pobierz paczkę ZIP (Etykiety i Karty)",
            data=st.session_state.zip_data,
            file_name="zalaczniki_eprel.zip",
            mime="application/zip"
        )
