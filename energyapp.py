import streamlit as st
import pandas as pd
import requests
import time
import io
import zipfile

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="EPREL Pro Link Generator", page_icon="⚡", layout="wide")

# --- MAPOWANIE GRUP PRODUKTOWYCH NA SLUGI URL ---
# Mapowanie na podstawie wartości 'productGroup' zwracanych przez API EPREL
EPREL_URL_MAP = {
    "SMARTPHONES_TABLETS": "smartphonestablets20231669",
    "DISHWASHERS": "dishwashers2019",
    "WASHING_MACHINES": "washingmachines2019",
    "WASHER_DRYERS": "washerdriers2019",
    "TUMBLE_DRYERS": "tumbledryers20232534",
    "REFRIGERATING_APPLIANCES": "refrigeratingappliances2019",
    "REFRIGERATING_APPLIANCES_DIRECT_SALES": "refrigeratingappliancesdirectsalesfunction",
    "TYRES": "tyres",
    "LIGHT_SOURCES": "lightsources",
    "ELECTRONIC_DISPLAYS": "electronicdisplays",
    "AIR_CONDITIONERS": "airconditioners",
    "OVENS": "ovens",
    "RANGE_HOODS": "rangehoods",
    "LOCAL_SPACE_HEATERS": "localspaceheaters",
    "PROFESSIONAL_REFRIGERATED_STORAGE_CABINETS": "professionalrefrigeratedstoragecabinets",
    "RESIDENTIAL_VENTILATION_UNITS": "residentialventilationunits",
    "SPACE_HEATERS": "spaceheaters",
    "SPACE_HEATER_PACKAGES": "spaceheaterpackages",
    "WATER_HEATERS": "waterheaters",
    "WATER_HEATER_PACKAGES": "waterheaterpackages",
    "HOT_WATER_STORAGE_TANKS": "hotwaterstoragetanks",
    "SOLID_FUEL_BOILERS": "solidfuelboilers",
    "SOLID_FUEL_BOILER_PACKAGES": "solidfuelboilerpackages"
}

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
                    "Kategoria (nowe pole)": "Nieznana",
                    "Klasa": "N/A",
                    "Bezpośredni Link PDF": "Błąd danych"
                }

                if eprel_id:
                    data = get_eprel_full_data(eprel_id, API_KEY)
                    if data:
                        # 1. Wyodrębnienie kategorii z API
                        group_name = data.get("productGroup", "OTHER")
                        res["Kategoria (nowe pole)"] = group_name
                        res["Klasa"] = data.get("energyClass", "N/A")
                        
                        # 2. Mapowanie kategorii na slug w URL[cite: 1]
                        url_category = EPREL_URL_MAP.get(group_name, "other")
                        
                        # 3. Specyficzna obsługa końcówki dla LIGHT_SOURCES[cite: 1]
                        if group_name == "LIGHT_SOURCES":
                            suffix = "_big_color.pdf"
                        else:
                            suffix = ".pdf"
                        
                        # 4. Tworzenie linku na podstawie pobranych danych
                        res["Bezpośredni Link PDF"] = f"https://eprel.ec.europa.eu/labels/{url_category}/Label_{eprel_id}{suffix}"

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
