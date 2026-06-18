import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from openai import OpenAI
import tiktoken
import io
import concurrent.futures

# Parametri crawling
PRIORITY_PATHS = ["/azienda", "/chi-siamo", "/about", "/company"]
RELEVANT_PATH_KEYWORDS = ["servizi", "prodotti", "solutions", "offerta", "settori", "soluzioni", "industria", "markets"]
EXCLUDED_PATH_KEYWORDS = [
    "privacy", "cookie", "termini", "terms", "policy", "faq", "press",
    "news", "blog", "login", "careers", "contatti", "contact",
    "lavora", "recruiting", "media"
]
STOP_WORD_COUNT = 1500

# === Crawling HTML ===
def get_html(url):
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
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    domain = urlparse(base_url).netloc
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        full_url = urljoin(base_url, href).split("#")[0].split("?")[0]
        if domain in urlparse(full_url).netloc:
            if not any(excl in full_url.lower() for excl in EXCLUDED_PATH_KEYWORDS):
                if not full_url.startswith("mailto:") and not full_url.endswith((".pdf", ".jpg", ".png")):
                    links.add(full_url)
    return links

def summarize_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for script in soup(["script", "style"]):
        script.extract()
    text_blocks = []
    for tag in soup.find_all(['p', 'li', 'h2', 'h3']):
        if tag and tag.get_text():
            content = tag.get_text().strip()
            text_blocks.append(content)
    return "\n".join(text_blocks)

def truncate_text(text, max_tokens=3000):
    tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
    tokens = tokenizer.encode(text)
    if len(tokens) > max_tokens:
        tokens = tokens[:max_tokens]
    return tokenizer.decode(tokens)

# === Generazione contenuti GPT ===
# Il client OpenAI viene creato in main() dalla chiave fornita dall'utente e
# passato qui come argomento: nessuna chiave è cablata nel codice.
def generate_detailed_summary(client, text, azienda):
    prompt = f"Analizza il testo e scrivi una breve descrizione oggettiva dell’azienda “{azienda}”: settore, offerta, mercato. Includi molteplici keywords in modo da ottimizzare la ricerca in base a parole chiave."
    content = text + "\n\n" + prompt
    try:
        print(f"Token descrizione: {len(tiktoken.encoding_for_model('gpt-3.5-turbo').encode(content))}")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": content}],
            max_tokens=200,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Errore OpenAI (descrizione) su {azienda}: {e}")
        return "Errore nella descrizione"

def generate_peak35_paragraph(client, text, nome_azienda="l'azienda", esempi=None):
    try:
        prompt = f"""
Scrivi un paragrafo di massimo 3-4 frasi per ciascuna delle aziende che ti indicherò seguendo le linee guida in basso.

Struttura del Paragrafo
Riconoscimento iniziale
Apri il paragrafo con un riconoscimento per i successi dell’azienda, utilizzando un tono apprezzativo ma professionale.
Esempi: "Prima di tutto, complimenti per il successo e la crescita della vostra azienda." / "Dalle nostre analisi, la vostra azienda si è distinta per..."

Punti distintivi
Evidenzia ciò che rende unica l’azienda, sottolineando caratteristiche specifiche e concrete.
Possibili aree di eccellenza: innovazione tecnologica, maestria artigianale, sostenibilità, adattabilità al mercato.
Esempi: "Grazie alla vostra attenzione alla sostenibilità..." / "La vostra capacità di coniugare tradizione e innovazione..."

Conclusione che esprime stima
Chiudi con una frase che valorizzi la posizione strategica e il potenziale futuro dell’azienda.
Esempi: "Il vostro approccio innovativo vi posiziona come un punto di riferimento nel settore." / "Siamo convinti che la vostra visione strategica vi permetterà di continuare a espandervi..."

Esempio Generale:
"Dalle nostre analisi, {nome_azienda} si distingue per [caratteristiche]. La vostra capacità di [punto di forza] vi posiziona come [ruolo strategico nel mercato], con prospettive di crescita significative."

Testo di riferimento (non citarlo direttamente):
{text}
Alcune cose da NON fare:
- NO descrizione troppo approfondita dei prodotti e dei servizi offerti, tieni a mente che il destinatario del messaggio conosce perfettamente la propria azienda
- NO certificazioni
- NO tono eccessivamente ampolloso o lusingatorio (bisogna dimostrare apprezzamento ma senza esagerare
- NO paragrafi troppo lunghi, sii sintetico

Rendi tutto coeso come se fosse un umano a scrivere.
Questi sono esempi finali:
Prima di tutto, complimenti per oltre vent’anni di servizio nella manutenzione di trattori agricoli e macchine industriali. L’impiego di tecnologie moderne e personale qualificato garantisce interventi rapidi e precisi. L’affidabilità costruita nel tempo vi rende officina di riferimento per il comparto agricolo bresciano.
Prima di tutto, complimenti per oltre mezzo secolo nel progettare cabine di sicurezza e vetri temperati per macchine operatrici. L’elevato grado di personalizzazione e le certificazioni tecniche vi rendono fornitori fidati di automotive, ferroviario e movimentazione industriale. Il connubio di esperienza e R&D vi assicura una posizione di riferimento duratura.

        """
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": prompt}],
            max_tokens=400,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Errore durante la generazione del paragrafo: {e}")
        return "Errore nella generazione"

# === Crawling sito web ===
def crawl_website(start_url, max_pages=3):
    visited = set()
    to_visit = [start_url]
    page_count = 0
    full_text = ""
    MAX_TEXT_LENGTH = 60000

    while to_visit and page_count < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue

        html = get_html(url)
        if html:
            page_text = summarize_html(html)
            full_text += page_text + "\n\n"
            if len(full_text.split()) > STOP_WORD_COUNT:
                break
            if len(full_text) > MAX_TEXT_LENGTH:
                full_text = full_text[:MAX_TEXT_LENGTH]
            links = extract_links(html, start_url)
            priority_links = sorted(
                [l for l in links if any(p in l.lower() for p in PRIORITY_PATHS)],
                key=lambda x: sum(k in x.lower() for k in RELEVANT_PATH_KEYWORDS),
                reverse=True
            )
            other_links = list(links - set(priority_links))
            to_visit.extend(priority_links + other_links)

            visited.add(url)
            page_count += 1

    return truncate_text(full_text, max_tokens=3000)

# === Streamlit App ===
def main():
    st.title("📊 Company Summary Generator")
    st.markdown(
        "Carica un file Excel con le colonne 'Azienda' e 'Sito'. "
        "Verranno generati la descrizione, il paragrafo Peak35 o entrambi."
    )

    # --- Bring-your-own-key ---
    # La chiave è fornita dall'utente, usata solo in questa sessione (in memoria)
    # e mai salvata, loggata o committata. Ogni visitatore usa la propria chiave.
    st.markdown(
        "🔑 **OpenAI API Key** — usata solo per questa sessione e mai salvata. "
        "Creane una su [platform.openai.com/api-keys](https://platform.openai.com/api-keys)."
    )
    api_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")

    scelta_output = st.selectbox(
        "Seleziona il tipo di output da generare:",
        ["Descrizione", "Paragrafo Peak35", "Entrambi"]
    )

    uploaded_file = st.file_uploader("📂 Carica file Excel con aziende", type=["xlsx"])
    esempi_file = st.file_uploader("📚 Carica file con esempi di paragrafi (facoltativo)", type=["xlsx"])
    max_pages = st.slider("Numero massimo di pagine da esplorare", 1, 5, 3)
    concurrency = st.slider("Numero massimo di aziende in parallelo", 1, 10, 4)

    # Caricamento esempi opzionale
    paragrafi_esempio = []
    if esempi_file:
        try:
            df_esempi = pd.read_excel(esempi_file)
            if "Paragrafo Esempio" in df_esempi.columns:
                paragrafi_esempio = df_esempi["Paragrafo Esempio"].dropna().tolist()
            else:
                st.warning("⚠️ Il file degli esempi deve avere una colonna 'Paragrafo Esempio'.")
        except Exception as e:
            st.error(f"Errore nel caricamento del file esempi: {e}")

    if uploaded_file and st.button("Avvia elaborazione"):
        if not api_key:
            st.error("⚠️ Inserisci la tua OpenAI API Key per avviare l'elaborazione.")
            st.stop()

        # Client creato dalla chiave dell'utente — l'oggetto OpenAI è thread-safe
        # e viene condiviso tra i thread tramite closure.
        client = OpenAI(api_key=api_key.strip())

        df = pd.read_excel(uploaded_file)
        if not {'Azienda', 'Sito'}.issubset(df.columns):
            st.error("Il file deve contenere le colonne 'Azienda' e 'Sito'.")
            return

        if "Descrizione" not in df.columns:
            df['Descrizione'] = ""
        if "Paragrafo Peak35" not in df.columns:
            df['Paragrafo Peak35'] = ""

        st.info(f"Totale aziende da processare: {len(df)}")
        progress = st.progress(0)
        status = st.empty()

        rows = list(df.iterrows())

        def process_row_threadsafe(idx, row):
            sito = str(row['Sito']).strip()
            nome_azienda = str(row['Azienda']).strip()
            if not sito.startswith("http"):
                sito = "http://" + sito
            try:
                testo = crawl_website(sito, max_pages=max_pages)
                if not testo or len(testo.strip()) < 50:
                    return idx, "Contenuto insufficiente", "Contenuto insufficiente"
                descrizione = (
                    generate_detailed_summary(client, testo, nome_azienda)
                    if scelta_output in ["Descrizione", "Entrambi"]
                    else "Non richiesto"
                )
                paragrafo = (
                    generate_peak35_paragraph(client, testo, nome_azienda, esempi=paragrafi_esempio)
                    if scelta_output in ["Paragrafo Peak35", "Entrambi"]
                    else "Non richiesto"
                )
                return idx, descrizione, paragrafo
            except Exception as e:
                return idx, f"Errore: {e}", f"Errore: {e}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(process_row_threadsafe, idx, row) for idx, row in rows]
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                idx, descrizione, paragrafo = future.result()
                df.at[idx, 'Descrizione'] = descrizione
                df.at[idx, 'Paragrafo Peak35'] = paragrafo
                progress.progress((i + 1) / len(df))
                status.text(f"Completate: {i + 1} di {len(df)} aziende")

        st.success("✅ Elaborazione completata!")
        st.dataframe(df)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)

        st.download_button(
            label="📥 Scarica risultati",
            data=output.getvalue(),
            file_name="risultati_descrizioni.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if __name__ == '__main__':
    main()
