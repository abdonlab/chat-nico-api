import json
import random
import base64
from pathlib import Path
import requests
import streamlit as st
import threading, time
#import pyttsx3, threading, time
import os

# ------------------ 🔊 Módulo de voz en tiempo real ------------------
def hablar_stream(texto):
    """Habla en tiempo real cada fragmento de texto con pausas naturales."""
    def _voz():
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 160)
            voces = engine.getProperty('voices')
            voz_encontrada = False
            for voz in voces:
                if ("spanish-mbrola-2" in voz.id.lower()) or ("mexican-mbrola-1" in voz.id.lower()):
                    engine.setProperty('voice', voz.id)
                    voz_encontrada = True
                    break
            if not voz_encontrada:
                engine.setProperty('voice', 'spanish-mbrola-2')

            engine.say(texto)
            engine.runAndWait()
            time.sleep(0.4)
        except Exception as e:
            print(f"Error de voz: {e}")

    hilo = threading.Thread(target=_voz)
    hilo.start()

# ------------------ 🌐 Búsqueda web inteligente ------------------
def buscar_en_web(pregunta):
    """Realiza una búsqueda rápida en español y devuelve hasta 200 caracteres."""
    try:
        st.info("🛰️ Buscando en la web...")
        url = f"https://api.duckduckgo.com/?q={pregunta}&format=json&kl=es-es"
        r = requests.get(url, timeout=8)
        data = r.json()
        resumen = data.get("AbstractText", "")
        if not resumen:
            related = data.get("RelatedTopics", [])
            if related and isinstance(related, list):
                for item in related:
                    if isinstance(item, dict) and item.get("Text"):
                        resumen = item["Text"]
                        break
        return resumen[:200] if resumen else ""
    except Exception as e:
        print(f"Error en búsqueda web: {e}")
        return ""

def necesita_internet(pregunta):
    """Detecta si la pregunta requiere conexión a Internet."""
    claves = ["quién es", "último", "actual", "reciente", "hoy", "noticias", "fecha", "presidente", "precio", "clima"]
    return any(palabra in pregunta.lower() for palabra in claves)

# ------------------ Config ------------------
st.set_page_config(page_title="Hola soy Nico tu asistente de la UMNSH", page_icon="🎬", layout="wide")
ROOT = Path(__file__).parent
VIDEO_DIR = ROOT / "videos"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# ------------------ Sidebar (modelo) ------------------
st.sidebar.header("⚙️ LLM / Google Gemini")
# API fija de Google Gemini (puedes cambiarla cuando quieras)
api_key ="AIzaSyD7ndVMuj8kSoHT8BI3QTFeRD6OtQ0qP1M"
st.sidebar.write("🔒 Usando clave integrada de Google AI Studio")
model = st.sidebar.selectbox(
    "Modelo",
    [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash-lite-001",

    ],
    index=0,
)
temperature = st.sidebar.slider("Temperature", 0.0, 1.5, 0.7, 0.05)
top_p = st.sidebar.slider("top_p", 0.05, 1.0, 0.90, 0.05)
max_tokens = st.sidebar.slider("Máx. tokens", 32, 2048, 200, 16)
system_prompt = st.sidebar.text_area(
    "System prompt",
    "Eres un asistente de la UMSNH. Responde claro, conciso y en 1–3 líneas."
)

# ------------------ Videos ------------------
exts = {".mp4", ".webm", ".ogg", ".ogv"}
videos = sorted([p for p in VIDEO_DIR.glob("*") if p.suffix.lower() in exts])
st.sidebar.caption(f"🎥 Videos encontrados: {len(videos)}")

def pick_video_data_uri(paths):
    if not paths:
        return None, None
    p = random.choice(paths)
    suffix = p.suffix.lower()
    mime = "video/mp4"
    if suffix == ".webm":
        mime = "video/webm"
    elif suffix in (".ogg", ".ogv"):
        mime = "video/ogg"
    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}", mime

# ------------------ Cliente de streaming hacia Google AI Studio ------------------
# ------------------ Cliente de streaming hacia Google AI Studio ------------------
def stream_gemini(api_key: str, model: str, prompt: str):
    """Streaming desde Google AI Studio (API Key directa, sin Vertex)."""
    version = "v1" if "2.0" in model else "v1beta"
    endpoint = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": float(temperature),
            "topP": float(top_p),
            "maxOutputTokens": int(max_tokens)
        }
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        if response.status_code != 200:
            yield {"response": f"⚠️ Error al conectar con Gemini: {response.text}"}
            yield {"done": True}
            return

        data = response.json()
        candidates = data.get("candidates", [])
        texto = ""
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            for p in parts:
                texto += p.get("text", "")

        for fragmento in texto.split(" "):
            yield {"response": fragmento + " "}
            time.sleep(0.04)
        yield {"done": True}

    except Exception as e:
        yield {"response": f"Error al conectar con Gemini: {e}"}
        yield {"done": True}
# ------------------ UI ------------------
st.title("Hola soy Nico tu asistente de la UMNSH")

question = st.text_input("Pregunta:", "")
send = st.button("Enviar")

if send and question.strip():
    # 🌐 Si necesita Internet
    contexto_web = ""
    if necesita_internet(question):
        contexto_web = buscar_en_web(question)
        if contexto_web:
            st.success("🌐 Se obtuvo información adicional de la web.")

    data_uri, mime = pick_video_data_uri(videos)
    if data_uri:
        video_html = f'''
        <div style="display:flex;justify-content:center;margin:10px 0;">
          <video id="encabezadoVideo" width="320" height="180" autoplay loop muted playsinline>
            <source src="{data_uri}" type="{mime}"/>
            Tu navegador no soporta video.
          </video>
        </div>
        '''
        st.markdown(video_html, unsafe_allow_html=True)
    else:
        st.warning("No hay videos en la carpeta 'Videos'. Sube .mp4/.webm/.ogg.")

    st.markdown(f"**Tú:** {question}")

    full_prompt = f"{system_prompt}\n\nInstrucción: {question}\n\nInformación web (si aplica): {contexto_web}\n\nassistant:"

    answer_box = st.empty()
    response_buf = ""
    try:
        for evt in stream_gemini(api_key, model, full_prompt):
            chunk = evt.get("response", "")
            if chunk:
                response_buf += chunk
                answer_box.markdown(f"**Nico:** {response_buf}")
                hablar_stream(chunk)
            if evt.get("done"):
                break
    except Exception as e:
        answer_box.error(f"Error: {e}")
    finally:
        pause_js = '''
        <script>
        const v = parent.document.getElementById('encabezadoVideo');
        if (v) { try { v.pause(); } catch(e){} }
        </script>
        '''
        st.components.v1.html(pause_js, height=0)
