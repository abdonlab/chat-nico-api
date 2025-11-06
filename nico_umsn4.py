import json
import random
import base64
from pathlib import Path
import requests
import streamlit as st
import threading, time
#import pyttsx3, threading, time
import os
from dotenv import load_dotenv

# ------------------ Configuración inicial ------------------
st.set_page_config(page_title="Hola soy Nico tu asistente de la UMNSH", page_icon="🎬", layout="wide")
ROOT = Path(__file__).parent
VIDEO_DIR = ROOT / "videos"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# ------------------ 🔊 Módulo de voz ------------------
def hablar_stream(texto):
    """Habla en tiempo real cada fragmento de texto con pausas naturales."""
    def _voz():
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', 160)
            voces = engine.getProperty('voices')
            voz_encontrada = False
            for voz in voces:
                if ("spanish" in voz.id.lower()) or ("mexican" in voz.id.lower()):
                    engine.setProperty('voice', voz.id)
                    voz_encontrada = True
                    break
            if not voz_encontrada:
                engine.setProperty('voice', voces[0].id)
            engine.say(texto)
            engine.runAndWait()
            time.sleep(0.4)
        except Exception as e:
            print(f"Error de voz: {e}")
    threading.Thread(target=_voz).start()

# ------------------ 🌐 Búsqueda web ------------------
def buscar_en_web(pregunta):
    """Realiza una búsqueda rápida en español y devuelve hasta 200 caracteres."""
    try:
        url = f"https://api.duckduckgo.com/?q={pregunta}&format=json&kl=es-es"
        r = requests.get(url, timeout=8)
        data = r.json()
        resumen = data.get("AbstractText", "")
        if not resumen:
            for item in data.get("RelatedTopics", []):
                if isinstance(item, dict) and item.get("Text"):
                    resumen = item["Text"]
                    break
        return resumen[:200] if resumen else ""
    except Exception as e:
        print(f"Error búsqueda web: {e}")
        return ""

def necesita_internet(pregunta):
    """Detecta si la pregunta requiere conexión a Internet."""
    claves = ["quién es", "último", "actual", "reciente", "hoy", "noticias", "fecha", "presidente", "precio", "clima"]
    return any(palabra in pregunta.lower() for palabra in claves)

# ------------------ Sidebar (modelo) ------------------
st.sidebar.header("⚙️ LLM / Google Gemini API")
st.sidebar.write("🔒 Conectado mediante API Key segura de Google AI Studio")

api_key = st.secrets["GEMINI_API_KEY"]# API Key de AI Studio
model = st.sidebar.selectbox(
    "Modelo",
    ["gemini-2.0-flash-lite-001"],
    index=0,
)
temperature = st.sidebar.slider("Temperature", 0.0, 1.5, 0.7, 0.05)
top_p = st.sidebar.slider("top_p", 0.05, 1.0, 0.90, 0.05)
max_tokens = st.sidebar.slider("Máx. tokens", 32, 2048, 200, 16)

# --- Prompt del sistema (oculto, no visible) ---
SYSTEM_PROMPT = """
Soy NICO, el asistente virtual institucional de la Universidad Michoacana de San Nicolás de Hidalgo (UMSNH).
Mi propósito es ayudar a estudiantes, docentes y personal administrativo a resolver dudas académicas, administrativas y tecnológicas de manera clara, rápida y confiable.
Si necesitas información oficial, puedes consultar www.umich.mx.
"""

# ------------------ Videos ------------------
exts = {".mp4", ".webm", ".ogg", ".ogv"}
videos = sorted([p for p in VIDEO_DIR.glob("*") if p.suffix.lower() in exts])
st.sidebar.caption(f"🎥 Videos encontrados: {len(videos)}")

def pick_video_data_uri(paths):
    if not paths: return None, None
    p = random.choice(paths)
    mime = "video/mp4" if p.suffix.lower() == ".mp4" else "video/webm"
    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}", mime

# ------------------ Cliente de streaming hacia Gemini ------------------
def stream_gemini(api_key: str, model: str, prompt: str):
    """Streaming desde Google AI Studio (API Key directa, sin Vertex)."""
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": float(temperature), "topP": float(top_p), "maxOutputTokens": int(max_tokens)},
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        if response.status_code != 200:
            yield {"response": f"⚠️ Error al conectar con Gemini: {response.text}"}
            yield {"done": True}
            return

        data = response.json()
        texto = ""
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                texto += part.get("text", "")
        for frag in texto.split(" "):
            yield {"response": frag + " "}
            time.sleep(0.04)
        yield {"done": True}

    except Exception as e:
        yield {"response": f"⚠️ Error: {e}"}
        yield {"done": True}

# ------------------ Interfaz principal ------------------
st.title("Hola, soy Nico tu asistente de la UMNSH")

question = st.text_input("Pregunta:")
send = st.button("Enviar")

if send and question.strip():
    contexto_web = buscar_en_web(question) if necesita_internet(question) else ""
    if contexto_web:
        st.success("🌐 Se obtuvo información adicional de la web.")

    data_uri, mime = pick_video_data_uri(videos)
    if data_uri:
        st.markdown(f"""
        <div style='display:flex;justify-content:center;margin:10px 0;'>
          <video width='320' height='180' autoplay loop muted playsinline>
            <source src='{data_uri}' type='{mime}'/>
          </video>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("No hay videos en la carpeta 'videos'.")

    st.markdown(f"*Tú:* {question}")
    full_prompt = f"{SYSTEM_PROMPT}\n\nUsuario: {question}\n\nContexto web: {contexto_web}"

    answer_box = st.empty()
    response_buf = ""

    for evt in stream_gemini(api_key, model, full_prompt):
        chunk = evt.get("response", "")
        if chunk:
            response_buf += chunk
            answer_box.markdown(f"*Nico:* {response_buf}")
            hablar_stream(chunk)

        if evt.get("done"):
            # Detener el video cuando la respuesta termina
            pause_js = """
            <script>
            const v = parent.document.querySelector('video');
            if (v) { v.pause(); v.currentTime = 0; }
            </script>
            """
            st.components.v1.html(pause_js, height=0)
            break
