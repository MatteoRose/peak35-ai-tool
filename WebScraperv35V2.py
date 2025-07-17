
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import openai
import os
import tiktoken
from dotenv import load_dotenv
import io

# Carica la API Key dal file .env
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ------------------------------
# FUNZIONI DI BASE
# ------------------------------

def get_html(url):
    """Scarica il contenuto HTML della pagina."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Errore durante il download della pagina {url}: {e}")
        return None

def extract_links(html, base_url):
    """Estrai i link interni dalla pagina."""
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        full_url = urljoin(base_url, href)
        # Rimuove ancore (#...) e parametri (?...)
        full_url = full_url.split("#")[0].split("?")[0]

        # Considera solo link interni (che contengono il dominio base_url)
        if base_url in full_url:
            links.add(full_url)
    return links

def summarize_html(html):
    """Pulisce il testo HTML e restituisce solo il contenuto leggibile."""
    soup = BeautifulSoup(html, "html.parser")
    # Rimuove script e style
    for script in soup(["script", "style"]):
        script.extract()

    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return "\n".join(chunk for chunk in chunks if chunk)

def truncate_text(text, max_tokens=4000):
    """Taglia il testo per rimanere entro i limiti di OpenAI (circa 4000 token)."""
    tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
    tokens = tokenizer.encode(text)

    if len(tokens) > max_tokens:
        tokens = tokens[:max_tokens]

    return tokenizer.decode(tokens)

def generate_summary(text):
    """Genera una sintesi usando OpenAI."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Riassumi il contenuto in modo conciso."},
                {"role": "user", "content": text}
            ],
            max_tokens=500
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Errore durante la generazione della sintesi: {e}")
        return None

# ------------------------------
# FUNZIONE PRINCIPALE DI CRAWL
# ------------------------------

def crawl_website_return_summary(start_url, max_pages=2):
    """
    Scansiona il sito (fino a max_pages link interni), raccoglie testo e
    genera una sintesi usando OpenAI. Restituisce la sintesi come stringa.
    """
    visited = set()
    to_visit = [start_url]
    page_count = 0
    full_text = ""
    MAX_TEXT_LENGTH = 50000  # Limite precauzionale per evitare eccessi di testo

    while to_visit and page_count < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue

        html = get_html(url)
        if html:
            # Estraggo il testo "pulito"
            page_text = summarize_html(html)
            full_text += page_text + "\n\n"

            # Se raggiungiamo il limite, tronchiamo
            if len(full_text) > MAX_TEXT_LENGTH:
                full_text = full_text[:MAX_TEXT_LENGTH]

            # Troviamo eventuali link interni
            links = extract_links(html, start_url)
            to_visit.extend(links - visited)

            visited.add(url)
            page_count += 1

    # Troncamento per sicurezza
    full_text = truncate_text(full_text, max_tokens=4000)

    # Generiamo la sintesi finale
    summary = generate_summary(full_text)
    return summary if summary else "Sintesi non disponibile."

# ------------------------------
# WEBAPP STREAMLIT
# ------------------------------

def main():
    st.title("Web Crawler & Summarizer")
    st.write("Carica un file Excel con le colonne 'Azienda' e 'Sito'. Verrà generata una sintesi dei contenuti del sito.")

    # Uploader del file Excel
    uploaded_file = st.file_uploader("Carica il tuo file Excel", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Errore nel caricamento dell'Excel: {e}")
            return

        # Controllo che esistano le colonne richieste
        if not {"Azienda", "Sito"}.issubset(df.columns):
            st.error("Il file deve contenere le colonne 'Azienda' e 'Sito'.")
            return

        # Scelta del numero di pagine da scansionare
        max_pages = st.slider("Numero di pagine interne da scansionare", 1, 5, 2)

        # Quando si clicca il pulsante "Avvia"
        if st.button("Avvia l'analisi"):
            # Creiamo una colonna per la sintesi
            df["Sintesi"] = ""

            with st.spinner("Elaborazione in corso..."):
                for idx, row in df.iterrows():
                    sito = str(row["Sito"]).strip()
                    
                    # Se manca l'http:// o https://, aggiungiamolo
                    if not sito.startswith("http"):
                        sito = "http://" + sito

                    try:
                        summary_text = crawl_website_return_summary(sito, max_pages=max_pages)
                        df.at[idx, "Sintesi"] = summary_text if summary_text else "Nessuna sintesi generata."
                    except Exception as err:
                        df.at[idx, "Sintesi"] = f"Errore: {err}"

            st.success("Analisi completata!")
            st.write("Ecco un'anteprima dei risultati:")
            st.dataframe(df)

            # Creiamo un buffer in memoria
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Risultati")

            st.download_button(
                label="Scarica il file Excel con le sintesi",
                data=output.getvalue(),
                file_name="sintesi_output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if __name__ == "__main__":
    main()


