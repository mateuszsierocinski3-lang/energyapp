import streamlit as st
import pandas as pd
import requests
import time
import io
import zipfile

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="EPREL Data & PDF Downloader", page_icon="⚡", layout="wide")

# --- FUNKCJE POMOCNICZE ---

def get_eprel_data(eprel_id, ean, api_key):
    """Pobiera dane produktu z API EPREL."""
    if eprel_id and str(eprel_id).lower() != 'nan' and str(eprel_id).strip() != "":
        url = f"https://eprel.ec.europa.eu/api/product/{eprel_id.strip()}"
    elif ean and str(ean).lower() != 'nan' and str(ean).strip() != "":
        url = f"https://eprel.ec.europa.eu/api/product/gtin/{ean.strip()}"
    else:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

def download_eprel_file(url, api_key):
    """Pobiera plik binarny (PDF) z API EPREL przy użyciu autoryzacji."""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            return response.content
        return None
    except Exception:
        return None

# --- UI STREAMLIT ---
st.title("⚡ EPREL Pro: Dane i Paczka PDF")
st.markdown("""
Aplikacja pobiera dane, generuje linki oraz przygotowuje paczkę ZIP zawierającą:
* **Etykiety Energetyczne (PDF)** w folderze `etykiety_pdf/`
* **Karty Produktu (PDF)** w folderze `karty_pdf/`
Pliki są nazywane numerem **EAN**.
""")

# Pobieranie klucza z Secrets (Streamlit Cloud)
try:
    API_KEY = st.secrets["EPREL_API_KEY"]
except Exception:
    st.error("Błąd: Nie znaleziono klucza 'EPREL_API_KEY' w Secrets!")
    st.stop()

uploaded_file = st.file_uploader("Załaduj plik Excel (wymagane kolumny: 'ean' oraz 'kod eprel')", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    cols_lower = [str(c).lower() for c in df_in.columns]
    
    if 'ean' not in cols_lower or 'kod eprel' not in cols_lower:
        st.error("Plik musi zawierać kolumny: 'ean' i 'kod eprel'")
    else:
        if st.button("Uruchom pobieranie PDF i danych"):
            final_data = []
            zip_buffer = io.BytesIO()
            progress_bar = st.progress(0)
            
            ean_col = [c for c in df_in.columns if c.lower() == 'ean'][0]
            code_col = [c for c in df_in.columns if c.lower() == 'kod eprel'][0]

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for i, row in df_in.iterrows():
                    ean_val = str(row[ean_col]).split('.')[0].strip() if pd.notnull(row[ean_col]) else f"brak_ean_{i}"
                    eprel_id_val = str(row[code_col]).split('.')[0].strip() if pd.notnull(row[code_col]) else ""
                    
                    entry = {
                        "EAN": ean_val,
                        "Klasa Energetyczna": "Brak",
                        "Link do produktu": "Brak",
                        "Status PDF": "Błąd"
                    }

                    data = get_eprel_data(eprel_id_val, ean_val, API_KEY)
                    
                    if data:
                        real_id = data.get("registrationNumber") or eprel_id_val
                        entry["Klasa Energetyczna"] = data.get("energyClass", "N/A")
                        entry["Link do produktu"] = f"https://eprel.ec.europa.eu/screen/product/productModel/{real_id}"
                        
                        # 1. Pobieranie Etykiety jako PDF
                        label_pdf_url = f"https://eprel.ec.europa.eu/api/product/{real_id}/label?format=PDF"
                        label_bits = download_eprel_file(label_pdf_url, API_KEY)
                        if label_bits:
                            zip_file.writestr(f"etykiety_pdf/{ean_val}.pdf", label_bits)
                        
                        # 2. Pobieranie Karty jako PDF
                        fiche_pdf_url = f"https://eprel.ec.europa.eu/api/product/{real_id}/fiches"
                        fiche_bits = download_eprel_file(fiche_pdf_url, API_KEY)
                        if fiche_bits:
                            zip_file.writestr(f"karty_pdf/{ean_val}.pdf", fiche_bits)
                        
                        entry["Status PDF"] = "Pobrano (Etykieta + Karta)"

                    final_data.append(entry)
                    progress_bar.progress((i + 1) / len(df_in))
                    time.sleep(0.05)

            st.session_state.results_df = pd.DataFrame(final_data)
            st.session_state.zip_data = zip_buffer.getvalue()
            st.success("Wszystkie dane i pliki PDF zostały przygotowane!")

# --- POBIERANIE ---
if 'results_df' in st.session_state:
    st.subheader("Podgląd i Pobieranie")
    st.dataframe(st.session_state.results_df, use_container_width=True)
    
    col1, col2 = st.columns(2)
    with col1:
        buf_excel = io.BytesIO()
        st.session_state.results_df.to_excel(buf_excel, index=False, engine='xlsxwriter')
        st.download_button("📥 Pobierz Excel", buf_excel.getvalue(), "raport_eprel.xlsx")
    
    with col2:
        st.download_button("📦 Pobierz folder ZIP (PDFy)", st.session_state.zip_data, "dokumenty_eprel_pdf.zip")
