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
    # 1. Próba wyszukania po Kodzie EPREL
    if eprel_id and str(eprel_id).lower() != 'nan' and str(eprel_id).strip() != "":
        url = f"https://eprel.ec.europa.eu/api/product/{eprel_id.strip()}"
    
    # 2. Jeśli brak EPREL, próba po GTIN (EAN)
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

def generate_links(eprel_id):
    """Tworzy standardowe linki EPREL dla etykiet i kart."""
    if not eprel_id or str(eprel_id).lower() == 'nan':
        return "Brak ID", "Brak ID"
    
    fiche = f"https://eprel.ec.europa.eu/screen/product/lightsources/{eprel_id}/fiches"
    label = f"https://eprel.ec.europa.eu/api/product/{eprel_id}/label"
    return fiche, label

# --- UI STREAMLIT ---
st.title("⚡ EPREL Data Scraper")
st.info("Aplikacja pobiera dane na podstawie kodu EPREL (priorytet) lub numeru EAN (GTIN).")

# Pobieranie klucza z Secrets (Streamlit Cloud)
try:
    API_KEY = st.secrets["EPREL_API_KEY"] # Klucz musi być w Secrets na Streamlit Cloud
except Exception:
    st.error("Błąd: Nie znaleziono klucza 'EPREL_API_KEY' w Secrets!")
    st.stop()

uploaded_file = st.file_uploader("Załaduj plik Excel (wymagane kolumny: 'ean' oraz 'kod eprel')", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    
    cols = [str(c).lower() for c in df_in.columns]
    if 'ean' not in cols or 'kod eprel' not in cols:
        st.error("Plik musi zawierać kolumny: 'ean' i 'kod eprel'")
    else:
        if st.button("Pobierz dane z EPREL"):
            final_data = []
            progress_bar = st.progress(0)
            
            ean_col = [c for c in df_in.columns if c.lower() == 'ean'][0]
            code_col = [c for c in df_in.columns if c.lower() == 'kod eprel'][0]

            for i, row in df_in.iterrows():
                # Oczyszczanie danych wejściowych
                ean_val = str(row[ean_col]).split('.')[0].strip() if pd.notnull(row[ean_col]) else ""
                eprel_id_val = str(row[code_col]).split('.')[0].strip() if pd.notnull(row[code_col]) else ""
                
                entry = {
                    "EAN": ean_val,
                    "Kod EPREL (Input)": eprel_id_val,
                    "Klasa Energetyczna": "Nie znaleziono",
                    "EPREL ID (Znalezione)": "N/A",
                    "Karta Produktu": "Błąd",
                    "Etykieta Energetyczna": "Błąd"
                }

                # Pobieranie danych (funkcja obsługuje oba endpointy)
                data = get_eprel_data(eprel_id_val, ean_val, API_KEY)
                
                if data:
                    # Wyciągamy rzeczywisty ID z EPREL (ważne, jeśli szukaliśmy po EAN)
                    real_id = data.get("registrationNumber") or eprel_id_val
                    entry["EPREL ID (Znalezione)"] = real_id
                    entry["Klasa Energetyczna"] = data.get("energyClass", "N/A")
                    
                    fiche_url, label_url = generate_links(real_id)
                    entry["Karta Produktu"] = fiche_url
                    entry["Etykieta Energetyczna"] = label_url
                
                final_data.append(entry)
                progress_bar.progress((i + 1) / len(df_in))
                time.sleep(0.1)

            st.session_state.results_df = pd.DataFrame(final_data)
            st.success("Przetwarzanie zakończone!")

if 'results_df' in st.session_state:
    st.subheader("Podgląd danych")
    st.dataframe(st.session_state.results_df)
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Pobierz gotowy raport Excel",
        data=buf.getvalue(),
        file_name="wyniki_eprel.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
