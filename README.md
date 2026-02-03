import streamlit as st
import pandas as pd
import requests
import time
import io

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="EPREL Data Downloader", page_icon="⚡", layout="wide")

# --- FUNKCJE POMOCNICZE ---

def get_eprel_data(eprel_id, api_key):
    """Pobiera dane produktu z API EPREL."""
    url = f"https://eprel.ec.europa.eu/api/product/{eprel_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        return None

def generate_links(eprel_id):
    """Tworzy standardowe linki EPREL dla etykiet i kart."""
    # Link do karty produktu (Product Fiche)
    fiche = f"https://eprel.ec.europa.eu/screen/product/lightsources/{eprel_id}/fiches"
    # Link do generowania etykiety (Label)
    label = f"https://eprel.ec.europa.eu/api/product/{eprel_id}/label"
    return fiche, label

# --- UI STREAMLIT ---
st.title("⚡ EPREL Data Scraper")
st.info("Aplikacja pobiera klasę energetyczną, kartę produktu i etykietę na podstawie kodu EPREL.")

# Pobieranie klucza z Secrets (Streamlit Cloud)
try:
    API_KEY = st.secrets["EPREL_API_KEY"]
except:
    st.error("Błąd: Nie znaleziono klucza 'EPREL_API_KEY' w Secrets!")
    st.stop()

uploaded_file = st.file_uploader("Załaduj plik Excel (wymagane kolumny: 'ean' oraz 'kod eprel')", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    
    # Walidacja kolumn
    cols = [str(c).lower() for c in df_in.columns]
    if 'ean' not in cols or 'kod eprel' not in cols:
        st.error("Plik musi zawierać kolumny: 'ean' i 'kod eprel'")
    else:
        if st.button("Pobierz dane z EPREL"):
            final_data = []
            progress_bar = st.progress(0)
            
            # Mapowanie kolumn (na wypadek różnej wielkości liter)
            ean_col = [c for c in df_in.columns if c.lower() == 'ean'][0]
            code_col = [c for c in df_in.columns if c.lower() == 'kod eprel'][0]

            for i, row in df_in.iterrows():
                ean = str(row[ean_col]).split('.')[0].strip()
                eprel_id = str(row[code_col]).split('.')[0].strip()
                
                entry = {
                    "EAN": ean,
                    "Kod EPREL": eprel_id,
                    "Klasa Energetyczna": "Błąd / Brak",
                    "Karta Produktu": "Błąd",
                    "Etykieta Energetyczna": "Błąd"
                }

                if eprel_id and eprel_id.lower() != 'nan':
                    data = get_eprel_data(eprel_id, API_KEY)
                    
                    if data:
                        entry["Klasa Energetyczna"] = data.get("energyClass", "N/A")
                        fiche_url, label_url = generate_links(eprel_id)
                        entry["Karta Produktu"] = fiche_url
                        entry["Etykieta Energetyczna"] = label_url
                
                final_data.append(entry)
                progress_bar.progress((i + 1) / len(df_in))
                time.sleep(0.1) # Delikatny delay dla stabilności API

            # Wyniki
            st.session_state.results_df = pd.DataFrame(final_data)
            st.success("Przetwarzanie zakończone!")

if 'results_df' in st.session_state:
    st.subheader("Podgląd danych")
    st.dataframe(st.session_state.results_df)
    
    # Export do Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Pobierz gotowy raport Excel",
        data=buf.getvalue(),
        file_name="wyniki_eprel.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
