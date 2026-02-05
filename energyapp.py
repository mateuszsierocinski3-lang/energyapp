import streamlit as st
import pandas as pd
import requests
import time
import io

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="EPREL Data Downloader", page_icon="⚡", layout="wide")

# --- FUNKCJE POMOCNICZE ---

def get_eprel_data(eprel_id, ean, api_key):
    """
    Pobiera dane produktu z API EPREL. 
    Najpierw próbuje po ID EPREL, jeśli brak - próbuje po EAN/GTIN.
    """
    # 1. Określenie endpointu
    if eprel_id and str(eprel_id).lower() != 'nan' and str(eprel_id).strip() != "":
        url = f"https://eprel.ec.europa.eu/api/product/{str(eprel_id).strip()}"
    elif ean and str(ean).lower() != 'nan' and str(ean).strip() != "":
        url = f"https://eprel.ec.europa.eu/api/product/gtin/{str(ean).strip()}"
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

def generate_links(eprel_id):
    """Tworzy bezpośrednie linki do pobrania dokumentów PDF."""
    if not eprel_id or str(eprel_id).lower() == 'nan':
        return "Brak ID", "Brak ID"
    
    # Karta produktu (Product Fiche) - format PDF, język polski
    fiche = f"https://eprel.ec.europa.eu/api/product/{eprel_id}/fiches?format=PDF&language=PL"
    
    # Etykieta energetyczna (Energy Label) - format PDF
    label = f"https://eprel.ec.europa.eu/api/product/{eprel_id}/label?format=PDF"
    
    return fiche, label

# --- UI STREAMLIT ---
st.title("⚡ EPREL Data Scraper")
st.info("Aplikacja pobiera dane, etykiety PDF i karty produktu na podstawie kodu EPREL lub numeru EAN (GTIN).")

# Pobieranie klucza z Secrets (Streamlit Cloud)
try:
    # Wykorzystuje zapisany klucz EPREL z sekcji Secrets
    API_KEY = st.secrets["EPREL_API_KEY"]
except Exception:
    st.error("Błąd: Nie znaleziono klucza 'EPREL_API_KEY' w Secrets!")
    st.stop()

uploaded_file = st.file_uploader("Załaduj plik Excel (wymagane kolumny: 'ean' oraz 'kod eprel')", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    
    # Mapowanie kolumn bez względu na wielkość liter
    cols_map = {c.lower(): c for c in df_in.columns}
    
    if 'ean' not in cols_map or 'kod eprel' not in cols_map:
        st.error("Plik musi zawierać kolumny: 'ean' i 'kod eprel'")
    else:
        if st.button("Pobierz dane z EPREL"):
            final_data = []
            progress_bar = st.progress(0)
            
            ean_col = cols_map['ean']
            code_col = cols_map['kod eprel']

            for i, row in df_in.iterrows():
                # Czyszczenie danych wejściowych
                ean_val = str(row[ean_col]).split('.')[0].strip() if pd.notnull(row[ean_col]) else ""
                eprel_id_val = str(row[code_col]).split('.')[0].strip() if pd.notnull(row[code_col]) else ""
                
                entry = {
                    "EAN": ean_val,
                    "Kod EPREL (Input)": eprel_id_val,
                    "Klasa Energetyczna": "Nie znaleziono",
                    "EPREL ID (Systemowy)": "N/A",
                    "Link: Karta Produktu (PDF)": "N/A",
                    "Link: Etykieta Energetyczna (PDF)": "N/A"
                }

                # Pobieranie danych z odpowiedniego endpointu
                data = get_eprel_data(eprel_id_val, ean_val, API_KEY)
                
                if data:
                    # Wyciągnięcie właściwego ID (istotne przy wyszukiwaniu po EAN)
                    real_id = data.get("registrationNumber")
                    entry["EPREL ID (Systemowy)"] = real_id
                    entry["Klasa Energetyczna"] = data.get("energyClass", "N/A")
                    
                    # Generowanie linków PDF
                    fiche_url, label_url = generate_links(real_id)
                    entry["Link: Karta Produktu (PDF)"] = fiche_url
                    entry["Link: Etykieta Energetyczna (PDF)"] = label_url
                
                final_data.append(entry)
                
                # Aktualizacja paska postępu
                progress_bar.progress((i + 1) / len(df_in))
                time.sleep(0.05) # Szybki delay dla API

            st.session_state.results_df = pd.DataFrame(final_data)
            st.success("Przetwarzanie zakończone!")

if 'results_df' in st.session_state:
    st.subheader("Podgląd wyników")
    st.dataframe(st.session_state.results_df)
    
    # Eksport do Excel z użyciem xlsxwriter (wymaga wpisu w requirements.txt)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Pobierz gotowy raport Excel",
        data=buf.getvalue(),
        file_name="wyniki_eprel_pdf.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
