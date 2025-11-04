import json, random, base64, requests, threading, time, os
from pathlib import Path
import streamlit as st
#from pyttsx3 import init as tts_init
from dotenv import load_dotenv
from vertexai import init
from vertexai.preview.generative_models import GenerativeModel

# --- Inicializa Vertex AI ---
init(project="sgc-prompts-umsnh-v1", location="us-central1")

# ------------------ 🔊 Módulo de voz en tiempo real ------------------
def hablar_stream(texto):
    """Habla en tiempo real cada fragmento de texto con pausas naturales."""
    try:
        import pyttsx3
        def _voz():
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", 160)
                voces = engine.getProperty("voices")
                for voz in voces:
                    if "spanish" in voz.id.lower():
                        engine.setProperty("voice", voz.id)
                        break
                engine.say(texto)
                engine.runAndWait()
                time.sleep(0.3)
            except Exception as e:
                print(f"Error de voz: {e}")
        threading.Thread(target=_voz).start()
    except Exception as e:
        print(f"Error inicializando voz: {e}")

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
            for item in data.get("RelatedTopics", []):
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

# ------------------ Configuración general ------------------
st.set_page_config(page_title="Hola soy Nico tu asistente de la UMNSH", page_icon="🎬", layout="wide")
ROOT = Path(__file__).parent
VIDEO_DIR = ROOT / "videos"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# ------------------ Sidebar ------------------
st.sidebar.header("⚙️ LLM / Google Gemini (Vertex AI)")
st.sidebar.write("🧠 Conectado al modelo institucional de Vertex AI")

model_name = st.sidebar.selectbox("Modelo", ["gemini-2.0-flash-lite-001"], index=0)
temperature = st.sidebar.slider("Temperature", 0.0, 1.5, 0.7, 0.05)
top_p = st.sidebar.slider("top_p", 0.05, 1.0, 0.9, 0.05)
max_tokens = st.sidebar.slider("Máx. tokens", 32, 2048, 200, 16)

SYSTEM_PROMPT = """
Soy NICO, el asistente virtual institucional de la Universidad Michoacana de San Nicolás de Hidalgo (UMSNH).
Mi propósito es ayudar a estudiantes, docentes y personal administrativo a resolver dudas académicas, administrativas y tecnológicas de manera clara, rápida y confiable.
Si necesitas información oficial, puedes consultar www.umich.mx.
"""

model = GenerativeModel(model_name)
st.sidebar.success(f"✅ Modelo activo en Vertex: {model_name}")

# ------------------ 🎥 Videos ------------------
exts = {".mp4", ".webm", ".ogg", ".ogv"}
videos = sorted([p for p in VIDEO_DIR.glob("*") if p.suffix.lower() in exts])
st.sidebar.caption(f"🎥 Videos encontrados: {len(videos)}")

def pick_video_data_uri(paths):
    if not paths: return None, None
    p = random.choice(paths)
    mime = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".ogg": "video/ogg",
        ".ogv": "video/ogg"
    }.get(p.suffix.lower(), "video/mp4")
    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}", mime

# ------------------ Cliente Vertex AI (stream simulado) ------------------
def stream_vertex(model: GenerativeModel, prompt: str):
    """Simula respuesta palabra por palabra usando Vertex AI."""
    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": float(temperature),
                "top_p": float(top_p),
                "max_output_tokens": int(max_tokens),
            },
        )
        texto = response.text or "⚠️ No se recibió respuesta del modelo."
        for palabra in texto.split(" "):
            yield {"response": palabra + " "}
            time.sleep(0.04)
        yield {"done": True}
    except Exception as e:
        yield {"response": f"⚠️ Error al conectar con Vertex AI: {e}"}
        yield {"done": True}

# ------------------ UI principal ------------------
st.title("Hola, soy Nico tu asistente de la UMSNH")
question = st.text_input("Pregunta:", "")
send = st.button("Enviar")

if send and question.strip():
    contexto_web = ""
    if necesita_internet(question):
        contexto_web = buscar_en_web(question)
        if contexto_web:
            st.success("🌐 Se obtuvo información adicional de la web.")

    data_uri, mime = pick_video_data_uri(videos)
    if data_uri:
        st.markdown(f"""
        <div style="display:flex;justify-content:center;margin:10px 0;">
          <video id="encabezadoVideo" width="320" height="180" autoplay loop muted playsinline>
            <source src="{data_uri}" type="{mime}"/>
            Tu navegador no soporta video.
          </video>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("No hay videos en la carpeta 'Videos'. Sube .mp4/.webm/.ogg.")

    st.markdown(f"**Tú:** {question}")

    full_prompt = f"{SYSTEM_PROMPT}\n\nInstrucción: {question}\n\nInformación web (si aplica): {contexto_web}\n\nassistant:"

    answer_box = st.empty()
    response_buf = ""
    try:
        for evt in stream_vertex(model, full_prompt):
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
        st.components.v1.html(
            "<script>const v=parent.document.getElementById('encabezadoVideo');if(v){try{v.pause();}catch(e){}};</script>",
            height=0,
        )
