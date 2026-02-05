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
    """Pobiera zawartość binarną pliku z API przy użyciu Tokena."""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        return resp.content if resp.status_code == 200 else None
    except:
        return None

# --- UI STREAMLIT ---
st.title("⚡ EPREL Pro: Dane, Linki i Załączniki")
st.info("Pobieranie klas energetycznych, generowanie linków produktowych oraz paczki ZIP z plikami PNG/PDF.")

# Pobieranie klucza z Secrets (pamiętaj o dodaniu EPREL_API_KEY w Streamlit Cloud)
try:
    API_KEY = st.secrets["EPREL_API_KEY"]
except Exception:
    st.error("Błąd: Nie znaleziono klucza 'EPREL_API_KEY' w Streamlit Secrets!")
    st.stop()

uploaded_file = st.file_uploader("Załaduj plik Excel (kolumny: 'ean', 'kod eprel')", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    cols = [str(c).lower() for c in df_in.columns]
    
    if 'ean' not in cols or 'kod eprel' not in cols:
        st.error("Plik musi zawierać kolumny: 'ean' i 'kod eprel'")
    else:
        if st.button("Uruchom proces"):
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
                        "Klasa Energetyczna": "Brak danych",
                        "Link do produktu": "Brak",
                        "Status plików": "Brak"
                    }
                    
                    data = get_eprel_data(eprel_id_val, ean_val, API_KEY)
                    
                    if data:
                        # 1. Pobieramy realny numer rejestracyjny
                        real_id = data.get("registrationNumber") or eprel_id_val
                        entry["Klasa Energetyczna"] = data.get("energyClass", "N/A")
                        
                        # 2. Generujemy czysty link do produktu (usuwamy /fiches i zbędne ścieżki)
                        # Format productModel jest uniwersalny i przekierowuje na właściwą kategorię
                        entry["Link do produktu"] = f"https://eprel.ec.europa.eu/screen/product/productModel/{real_id}"
                        
                        # 3. Pobieranie plików do ZIP (z tokenem)
                        label_url = f"https://eprel.ec.europa.eu/api/product/{real_id}/label?format=PNG"
                        fiche_url = f"https://eprel.ec.europa.eu/api/product/{real_id}/fiches"
                        
                        img_content = download_file(label_url, API_KEY)
                        if img_content:
                            zip_file.writestr(f"etykiety/{ean_val}.png", img_content)
                            
                        pdf_content = download_file(fiche_url, API_KEY)
                        if pdf_content:
                            zip_file.writestr(f"karty/{ean_val}.pdf", pdf_content)
                        
                        entry["Status plików"] = "Pobrano"
                    
                    final_data.append(entry)
                    progress_bar.progress((i + 1) / len(df_in))
                    time.sleep(0.05)

            st.session_state.results_df = pd.DataFrame(final_data)
            st.session_state.zip_data = zip_buffer.getvalue()
            st.success("Gotowe!")

# --- WYŚWIETLANIE I POBIERANIE ---
if 'results_df' in st.session_state:
    st.subheader("Podgląd wyników")
    # LinkColumn sprawia, że linki w tabeli Streamlit są klikalne
    st.dataframe(
        st.session_state.results_df,
        column_config={"Link do produktu": st.column_config.LinkColumn()}
    )
    
    c1, c2 = st.columns(2)
    with c1:
        buf = io.BytesIO()
        st.session_state.results_df.to_excel(buf, index=False, engine='xlsxwriter')
        st.download_button("📥 Pobierz Excel", buf.getvalue(), "eprel_raport.xlsx")
        
    with c2:
        st.download_button("📦 Pobierz ZIP (pliki {EAN})", st.session_state.zip_data, "zalaczniki_eprel.zip")
