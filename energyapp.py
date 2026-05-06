import streamlit as st
import pandas as pd
import requests
import time
import io
import zipfile

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="EPREL Pro Link Generator", page_icon="⚡", layout="wide")

# --- SPECJALNE KATEGORIE ---
# API EPREL zwraca productGroup już jako slug URL gotowy do użycia w linkach
# (np. "smartphonestablets20231669", "dishwashers2019", "lightsources")
# Jedyne co trzeba rozpoznać osobno to LIGHT_SOURCES – mają inny sufiks PDF
LIGHT_SOURCES_SLUG = "lightsources"

# --- FUNKCJE POMOCNICZE ---

def get_eprel_full_data(eprel_id, api_key):
    """Pobiera dane techniczne produktu z API."""
    if not eprel_id or str(eprel_id).lower() == 'nan':
        return None
    
    url = f"https://eprel.ec.europa.eu/api/product/{str(eprel_id).strip()}"
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

# --- UI STREAMLIT ---
st.title("⚡ EPREL: Generator Kategorii i Linków Label PDF")
st.markdown("Skrypt automatycznie rozpoznaje kategorię i generuje poprawny link PDF (w tym format big_color dla źródeł światła).")

# Pobieranie klucza z Secrets
try:
    API_KEY = st.secrets["EPREL_API_KEY"]
except Exception:
    st.error("Błąd: Brak 'EPREL_API_KEY' w Streamlit Secrets!")
    st.stop()

uploaded_file = st.file_uploader("Wgraj plik Excel (kolumny: 'ean', 'kod eprel')", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    cols_lower = {str(c).lower(): c for c in df_in.columns}
    
    if 'ean' not in cols_lower or 'kod eprel' not in cols_lower:
        st.error("Plik musi zawierać kolumny 'ean' oraz 'kod eprel'!")
    else:
        if st.button("Uruchom generowanie linków"):
            final_results = []
            progress_bar = st.progress(0)
            
            ean_col = cols_lower['ean']
            code_col = cols_lower['kod eprel']

            for i, row in df_in.iterrows():
                ean_val = str(row[ean_col]).split('.')[0].strip() if pd.notnull(row[ean_col]) else f"brak_{i}"
                eprel_id = str(row[code_col]).split('.')[0].strip() if pd.notnull(row[code_col]) else ""
                
                res = {
                    "EAN": ean_val,
                    "Kod EPREL": eprel_id,
                    "Kategoria (slug EPREL)": "Nieznana",
                    "Klasa": "N/A",
                    "Bezpośredni Link PDF": "Błąd danych"
                }

                if eprel_id:
                    data = get_eprel_full_data(eprel_id, API_KEY)
                    if data:
                        # 1. API zwraca productGroup już jako slug URL (np. "smartphonestablets20231669")
                        url_slug = data.get("productGroup", "other")
                        res["Kategoria (slug EPREL)"] = url_slug
                        res["Klasa"] = data.get("energyClass", "N/A")

                        # 2. Specjalny sufiks dla źródeł światła
                        if url_slug == LIGHT_SOURCES_SLUG:
                            suffix = "_big_color.pdf"
                        else:
                            suffix = ".pdf"

                        # 3. Tworzenie linku – slug z API trafia bezpośrednio do URL
                        res["Bezpośredni Link PDF"] = f"https://eprel.ec.europa.eu/labels/{url_slug}/Label_{eprel_id}{suffix}"

                final_results.append(res)
                progress_bar.progress((i + 1) / len(df_in))
                time.sleep(0.01)

            # Zapis wyników do sesji
            st.session_state.results_df = pd.DataFrame(final_results)
            st.success("Przetwarzanie zakończone!")

# --- WYŚWIETLANIE I POBIERANIE ---
if 'results_df' in st.session_state:
    st.subheader("Podgląd wygenerowanych danych")
    st.dataframe(st.session_state.results_df, use_container_width=True)
    
    # Export do Excela
    buf_excel = io.BytesIO()
    with pd.ExcelWriter(buf_excel, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Pobierz raport Excel z linkami i kategoriami",
        data=buf_excel.getvalue(),
        file_name="eprel_linki_pdf.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
