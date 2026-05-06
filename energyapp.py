import streamlit as st
import pandas as pd
import requests
import time
import io
import zipfile

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="EPREL Data & Link Generator", page_icon="⚡", layout="wide")

# --- MAPOWANIE KATEGORII NA FRAGMENTY URL ---
# Mapowanie na podstawie nazw grup produktów zwracanych przez API EPREL
CATEGORY_MAP = {
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

def download_eprel_file(url, api_key):
    """Pobiera plik binarny."""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        return response.content if response.status_code == 200 else None
    except:
        return None

# --- UI STREAMLIT ---
st.title("⚡ EPREL Pro: Generator Linków i Kategorii")

try:
    API_KEY = st.secrets["EPREL_API_KEY"]
except Exception:
    st.error("Błąd: Nie znaleziono klucza 'EPREL_API_KEY' w Secrets!")
    st.stop()

uploaded_file = st.file_uploader("Załaduj plik Excel (wymagane: 'ean', 'kod eprel')", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    cols_lower = [str(c).lower() for c in df_in.columns]
    
    if 'ean' not in cols_lower or 'kod eprel' not in cols_lower:
        st.error("Plik musi zawierać kolumny: 'ean' i 'kod eprel'")
    else:
        if st.button("Generuj dane i linki"):
            final_data = []
            zip_buffer = io.BytesIO()
            progress_bar = st.progress(0)
            
            ean_col = [c for c in df_in.columns if c.lower() == 'ean'][0]
            code_col = [c for c in df_in.columns if c.lower() == 'kod eprel'][0]

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for i, row in df_in.iterrows():
                    ean_val = str(row[ean_col]).split('.')[0].strip() if pd.notnull(row[ean_col]) else f"brak_{i}"
                    eprel_id_val = str(row[code_col]).split('.')[0].strip() if pd.notnull(row[code_col]) else ""
                    
                    entry = {
                        "EAN": ean_val,
                        "Kod EPREL": eprel_id_val,
                        "Kategoria EPREL": "Nieznana",
                        "Klasa": "N/A",
                        "Bezpośredni Link PDF": "Nie udało się wygenerować",
                        "Publiczny Link": "Brak"
                    }

                    data = get_eprel_data(eprel_id_val, ean_val, API_KEY)
                    
                    if data:
                        real_id = data.get("registrationNumber") or eprel_id_val
                        group_key = data.get("productGroup", "")
                        entry["Kategoria EPREL"] = group_key
                        entry["Klasa"] = data.get("energyClass", "N/A")
                        entry["Publiczny Link"] = f"https://eprel.ec.europa.eu/screen/product/productModel/{real_id}"
                        
                        # --- GENEROWANIE LINKU PDF NA PODSTAWIE KATEGORII ---
                        cat_slug = CATEGORY_MAP.get(group_key, "other")
                        # Specjalny przypadek dla źródeł światła (często mają _big_color)
                        suffix = "_big_color.pdf" if group_key == "LIGHT_SOURCES" else ".pdf"
                        entry["Bezpośredni Link PDF"] = f"https://eprel.ec.europa.eu/labels/{cat_slug}/Label_{real_id}{suffix}"

                        # --- POBIERANIE DO ZIP (opcjonalnie) ---
                        label_bits = download_eprel_file(f"https://eprel.ec.europa.eu/api/product/{real_id}/label?format=PNG", API_KEY)
                        if label_bits:
                            zip_file.writestr(f"etykiety/{ean_val}.png", label_bits)

                    final_data.append(entry)
                    progress_bar.progress((i + 1) / len(df_in))

            st.session_state.results_df = pd.DataFrame(final_data)
            st.session_state.zip_data = zip_buffer.getvalue()
            st.success("Zakończono!")

# --- WYNIKI ---
if 'results_df' in st.session_state:
    st.dataframe(st.session_state.results_df)
    
    buf_excel = io.BytesIO()
    with pd.ExcelWriter(buf_excel, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    
    st.download_button("📥 Pobierz Excel z linkami i kategoriami", buf_excel.getvalue(), "eprel_linki.xlsx")
