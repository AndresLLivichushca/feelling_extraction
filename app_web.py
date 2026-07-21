import streamlit as st
import multiprocessing as mp
from multiprocessing import Queue, Process, Event
import csv
import os
from datetime import datetime
import time
from playwright.sync_api import sync_playwright
import queue
import re
import json
import matplotlib.pyplot as plt

# Detección dinámica de entorno (Headless para Render/Docker, Visible para Local)
IS_PRODUCTION = os.getenv("RENDER") is not None or os.getenv("DOCKER_CONTAINER") is not None

# -------------------------------------------------------------
# CONFIGURACIÓN INICIAL Y CONTROL DE ESTADOS (CORE)
# -------------------------------------------------------------
st.set_page_config(page_title="Extracción de Sentimientos", layout="wide")

# Inicialización inmediata y global en cabecera para evitar AttributeError en renderizado dinámico
if "running_processes" not in st.session_state: 
    st.session_state.running_processes = []
if "log_messages" not in st.session_state: 
    st.session_state.log_messages = []

def add_web_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.log_messages.append(f"[{timestamp}] {message}")

# -------------------------------------------------------------
# FUNCIONES NATIVAS DE LIMPIEZA Y ESCRITURA CORE
# -------------------------------------------------------------

def clean_text(text):
    if not isinstance(text, str):
        return str(text)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F" "\U0001F300-\U0001F5FF" "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF" "\U00002702-\U000027B0" "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF" "\U0001FA00-\U0001FA6F" "\U0001FA70-\U0001FAFF"
        "\U00002600-\U000026FF" "\U00002700-\U000027BF" "\U0001F004-\U0001F0CF"
        "]+", flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    text = text.encode('utf-8', errors='ignore').decode('utf-8')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def csv_writer_process(result_queue, stop_event, filename="resultados.csv"):
    fieldnames = ['RedSocial', 'IDP', 'Request', 'FechaPeticion', 'FechaPublicacion', 'idPublicacion', 'Data']
    file_exists = os.path.exists(filename) and os.path.getsize(filename) > 0
    with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        while not stop_event.is_set() or not result_queue.empty():
            try:
                data = result_queue.get(timeout=1)
                cleaned_data = {k: clean_text(v) if isinstance(v, str) else v for k, v in data.items()}
                writer.writerow(cleaned_data)
                csvfile.flush()
            except queue.Empty:
                continue

def run_llm_process(network, result_queue):
    try:
        if network == "Threads":
            from LLM.sentiment_analyzer_threads import start_threads_analysis
            reporte = start_threads_analysis("resultados.csv")
            result_queue.put((network, reporte))
        elif network == "Instagram":
            from LLM.sentiment_analyzer_instagram import start_instagram_analysis
            reporte = start_instagram_analysis("resultados.csv")
            result_queue.put((network, reporte))
        elif network == "YouTube":
            from LLM.sentiment_analyzer_youtube import start_youtube_analysis
            reporte = start_youtube_analysis("resultados.csv")
            result_queue.put((network, reporte))
        elif network == "Reddit":
            from LLM.sentiment_analyzer_reddit import start_reddit_analysis
            reporte = start_reddit_analysis("resultados.csv")
            result_queue.put((network, reporte))
    except Exception as e:
        result_queue.put((network, f"Error crítico en LLM {network}: {e}"))

def run_scraper(network, query, max_posts, result_queue, stop_event, process_id):
    with sync_playwright() as p:
        # Se activa headless de forma dinámica dependiendo del entorno
        browser = p.chromium.launch(headless=IS_PRODUCTION)
        
        archivo_estado = f"{network.lower()}_state.json"
        archivo_cookies = f"{network.lower()}_cookies.json"
        
        context_args = {
            'viewport': {'width': 1280, 'height': 720},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }
        
        if os.path.exists(archivo_estado) and os.path.getsize(archivo_estado) > 0:
            context_args['storage_state'] = archivo_estado
            
        context = browser.new_context(**context_args)
        
        if 'storage_state' not in context_args and os.path.exists(archivo_cookies) and os.path.getsize(archivo_cookies) > 0:
            try:
                with open(archivo_cookies, 'r', encoding='utf-8') as f:
                    context.add_cookies(json.load(f))
            except Exception as e:
                print(f"[{network}] Advertencia al cargar cookies: {e}")
                
        page = context.new_page()
        try:
            if network == "YouTube":
                from process.Process_YouTube import YouTubeScraper
                YouTubeScraper(query, result_queue, stop_event, max_posts).run(page)
            elif network == "Reddit":
                from process.Process_Reddit import RedditScraper
                RedditScraper(query, result_queue, stop_event, max_posts).run(page)
            elif network == "Instagram":
                from process.Process_Instagram import InstagramScraper
                InstagramScraper(query, result_queue, stop_event, max_posts).run(page)
            elif network == "Threads":
                from process.Process_Threads import ThreadsScraper
                ThreadsScraper(query, result_queue, stop_event, max_posts).run(page)
        except Exception as e:
            print(f"Error en {network}: {e}")
        finally:
            browser.close()

def parse_report_counts(filepath, nombre_red):
    if not os.path.exists(filepath): return None
    counts = {"Positivo": 0, "Negativo": 0, "Neutral": 0}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^[•\-\*]?\s*(Positivo|Negativo|Neutral)\s*:\s*(\d+)", line.strip(), re.IGNORECASE)
                if m: counts[m.group(1).capitalize()] = int(m.group(2))
    except: return None
    return counts

def parse_report_times(filepath, nombre_red):
    if not os.path.exists(filepath): return None
    times = {"tiempo_total": 0.0, "tiempo_promedio": 0.0}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                m_total = re.search(r"Tiempo Total(?: de Procesamiento)?\s*:\s*([0-9]+(?:\.[0-9]+)?)", line, re.IGNORECASE)
                if m_total: times["tiempo_total"] = float(m_total.group(1))
                m_avg = re.search(r"Tiempo Promedio(?: por Publicación)?(?:/Post)?\s*:\s*([0-9]+(?:\.[0-9]+)?)", line, re.IGNORECASE)
                if m_avg: times["tiempo_promedio"] = float(m_avg.group(1))
    except: return None
    return times

# -------------------------------------------------------------
# INYECCIÓN DE ESTILOS CSS AVANZADOS (DASHBOARD LOOK)
# -------------------------------------------------------------
st.markdown("""
    <style>
        /* Ajustes globales de espaciado y fuentes */
        h1 { font-size: 42px !important; font-weight: 800 !important; letter-spacing: -1px; margin-bottom: 5px !important; }
        h2 { font-size: 32px !important; font-weight: 700 !important; margin-bottom: 15px !important; }
        h3 { font-size: 24px !important; font-weight: 600 !important; margin-bottom: 12px !important; }
        .stMarkdown p { font-size: 18px !important; line-height: 1.6 !important; }
        .block-container { padding-top: 3rem !important; padding-bottom: 5rem !important; padding-left: 5rem !important; padding-right: 5rem !important; }
        .stButton>button { height: 3.5rem !important; font-size: 18px !important; font-weight: bold !important; border-radius: 8px !important; }
        div[data-testid="stTextInput"] input { height: 3.2rem !important; font-size: 18px !important; }
        div[data-testid="stNumberInput"] input { height: 3.2rem !important; font-size: 18px !important; }

        /* REESTRUCTURACIÓN DEL MENÚ DE NAVEGACIÓN EN SIDEBAR */
        div[data-testid="stSidebarUserContent"] div[role="radiogroup"] label[data-testid="stWidgetLabel"] { display: none !important; }
        div[data-testid="stSidebarUserContent"] div[role="radiogroup"] { gap: 22px !important; }
        div[data-testid="stSidebarUserContent"] div[role="radiogroup"] label {
            background-color: #1a1f2c !important; padding: 18px 24px !important; border-radius: 8px !important;
            border: 1px solid #2d3748 !important; min-width: 100% !important; transition: all 0.3s ease-on-out !important;
            cursor: pointer !important; display: flex !important; align-items: center !important;
        }
        div[data-testid="stSidebarUserContent"] div[role="radiogroup"] label div:first-child[dir="ltr"] { display: none !important; }
        div[data-testid="stSidebarUserContent"] div[role="radiogroup"] label:hover {
            background-color: #242c3d !important; border-color: #4a5568 !important; box-shadow: 0px 6px 16px rgba(0, 0, 0, 0.3) !important; transform: translateY(-2px) !important;
        }
        div[data-testid="stSidebarUserContent"] div[role="radiogroup"] label[data-checked="true"] {
            background-color: #1c3d5a !important; border-color: #3182ce !important; box-shadow: 0px 0px 18px rgba(49, 130, 206, 0.45) !important;
        }
        div[data-testid="stSidebarUserContent"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
            color: #ffffff !important; font-size: 16px !important; font-weight: 600 !important; margin: 0px !important;
        }
    </style>
""", unsafe_allow_html=True)

# Encabezados de Marca de la barra lateral
st.sidebar.markdown('<p style="font-size:30px; font-weight:bold; color:#ffffff; margin-bottom:0px; letter-spacing:-1px;">⚡ Extracción de Sentimientos</p>', unsafe_allow_html=True)
st.sidebar.markdown('<p style="font-size:11px; color:#5f758a; margin-top:0px; margin-bottom:30px; font-weight:700; letter-spacing:1px;">SISTEMA DE NAVEGACIÓN</p>', unsafe_allow_html=True)

modulos = [
    "⚙️ Panel de Inyección (Scraping)",
    "🗂️ Explorador de Datos",
    "📊 Visión Global",
    "📈 Por Plataforma",
    "🤖 Storytelling AI"
]
modulo_activo = st.sidebar.radio("Navegación", modulos, label_visibility="collapsed")

# -------------------------------------------------------------
# PARSEO DE MÉTRICAS GLOBALES PARA TARJETAS KPI
# -------------------------------------------------------------
redes_reporte = [
    ("Instagram", "reporte_instagram_openai.txt"),
    ("YouTube", "reporte_youtube.txt"),
    ("Threads", "reporte_threads.txt"),
    ("Reddit", "reporte_reddit.txt")
]

g_pos, g_neg, g_neu, g_total = 0, 0, 0, 0
distribucion_redes = {}

for nombre, archivo in redes_reporte:
    stats = parse_report_counts(archivo, nombre)
    if stats:
        p, n, ne = stats.get("Positivo", 0), stats.get("Negativo", 0), stats.get("Neutral", 0)
        g_pos += p
        g_neg += n
        g_neu += ne
        distribucion_redes[nombre] = p + n + ne

g_total = g_pos + g_neg + g_neu
pct_pos = round((g_pos / g_total) * 100, 1) if g_total > 0 else 0.0
pct_neu = round((g_neu / g_total) * 100, 1) if g_total > 0 else 0.0
pct_neg = round((g_neg / g_total) * 100, 1) if g_total > 0 else 0.0

# -------------------------------------------------------------
# DESPLIEGUE POR MÓDULO SELECCIONADO
# -------------------------------------------------------------

# MÓDULO 1: PANEL DE INYECCIÓN (SCRAPING)
if modulo_activo == "⚙️ Panel de Inyección (Scraping)":
    st.markdown('<p style="font-size: 38px; font-weight: bold; margin-bottom:0px; letter-spacing:-0.5px;">Panel de Inyección y Cosecha Paralela</p>', unsafe_allow_html=True)
    st.markdown('<p style="font-size: 18px; color: #7f8c8d; margin-top:5px; margin-bottom:40px;">Orquestador centralizado de hilos del S.O. y buffers multiproceso de extracción de Threads, YT, IG y Reddit.</p>', unsafe_allow_html=True)
    
    query_sub = st.text_input("Palabra Clave Temática de Búsqueda", placeholder="Ej: Inteligencia Artificial...")
    max_p = st.number_input("Muestra de Posts Solicitados por Red", min_value=1, max_value=100, value=10)
    
    c1, c2 = st.columns(2)
    if c1.button("Lanzar Motores Paralelos Playwright", type="primary", use_container_width=True):
        if not query_sub.strip(): st.error("Ingresa una consulta válida.")
        else:
            stop_event = Event()
            res_q = Queue()
            p_writer = Process(target=csv_writer_process, args=(res_q, stop_event))
            p_writer.start()
            st.session_state.running_processes.append(p_writer)
            
            redes_seleccionadas = ["Instagram", "Threads", "YouTube", "Reddit"]
            for i, net in enumerate(redes_seleccionadas):
                p = Process(target=run_scraper, args=(net, query_sub, max_p, res_q, stop_event, i))
                p.start()
                st.session_state.running_processes.append(p)
            st.success("Motores asíncronos distribuidos en paralelo.")
            
    if c2.button("Lanzar Clasificación Sintáctica de Sentimientos (AI)", use_container_width=True):
        if not os.path.exists("resultados.csv"): st.error("No hay archivo base resultados.csv.")
        else:
            llm_q = Queue()
            hilos_llm = []
            redes_seleccionadas = ["Instagram", "Threads", "YouTube", "Reddit"]
            for net in redes_seleccionadas:
                p = Process(target=run_llm_process, args=(net, llm_q))
                p.start()
                hilos_llm.append(p)
            for p in hilos_llm: p.join()
            
            try:
                from LLM.storytelling_engine import generar_storytelling_global
                informe_premium = generar_storytelling_global()
                with open("reporte_storytelling_premium.md", "w", encoding="utf-8") as f: f.write(informe_premium)
            except: pass
            st.success("Pipeline sintáctico de lenguaje natural finalizado.")

   
# MÓDULO 2: EXPLORADOR DE DATOS
elif modulo_activo == "🗂️ Explorador de Datos":
    st.markdown('<p style="font-size: 38px; font-weight: bold; margin-bottom:0px; letter-spacing:-0.5px;">Explorador de Datos Estructurados</p>', unsafe_allow_html=True)
    archivos_json = [
        ("Instagram", "analisis_instagram_completo.json"),
        ("YouTube", "analisis_youtube_completo.json"),
        ("Threads", "analisis_threads_completo.json"),
        ("Reddit", "analisis_reddit_completo.json")
    ]
    tabs_ui = st.tabs([n for n, _ in archivos_json])
    for idx, (nombre, archivo) in enumerate(archivos_json):
        with tabs_ui[idx]:
            st.markdown("<br>", unsafe_allow_html=True)
            if os.path.exists(archivo):
                with open(archivo, "r", encoding="utf-8") as f: data = json.load(f)
                rows = [{
                    "ID Publicación": item.get("idPublicacion"),
                    "Sentimiento General": item.get("sentimiento_general"),
                    "Sentimiento Post": (item.get("analisis_post") or {}).get("sentimiento"),
                    "Total Comentarios": item.get("total_comentarios", 0),
                    "Analizados": item.get("total_analizados", 0)
                } for item in data[:100]]
                st.dataframe(rows, use_container_width=True)
            else: st.info(f"Sin registros para {nombre}.")

# MÓDULO 3: VISIÓN GLOBAL (DASHBOARD)
elif modulo_activo == "📊 Visión Global":
    st.markdown('<p style="font-size: 38px; font-weight: bold; margin-bottom:0px; letter-spacing:-0.5px;">Visión Global Unificada</p>', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(f'<div style="background-color:#14291c; padding:30px; border-radius:10px; border-left:6px solid #2ecc71;"><p style="margin:0; font-size:14px; color:#9bcca4; font-weight:bold; letter-spacing:0.5px;">POSITIVO</p><p style="margin:0; font-size:38px; font-weight:bold; color:#2ecc71; margin-top:5px;">{pct_pos}%</p></div>', unsafe_allow_html=True)
    k2.markdown(f'<div style="background-color:#262626; padding:30px; border-radius:10px; border-left:6px solid #95a5a6;"><p style="margin:0; font-size:14px; color:#cccccc; font-weight:bold; letter-spacing:0.5px;">NEUTRO</p><p style="margin:0; font-size:38px; font-weight:bold; color:#ffffff; margin-top:5px;">{pct_neu}%</p></div>', unsafe_allow_html=True)
    k3.markdown(f'<div style="background-color:#3a1818; padding:30px; border-radius:10px; border-left:6px solid #e74c3c;"><p style="margin:0; font-size:14px; color:#dfb1b1; font-weight:bold; letter-spacing:0.5px;">NEGATIVO</p><p style="margin:0; font-size:38px; font-weight:bold; color:#e74c3c; margin-top:5px;">{pct_neg}%</p></div>', unsafe_allow_html=True)
    k4.markdown(f'<div style="background-color:#121f2d; padding:30px; border-radius:10px; border-left:6px solid #3498db;"><p style="margin:0; font-size:14px; color:#a2b9cc; font-weight:bold; letter-spacing:0.5px;">MUESTRA TOTAL</p><p style="margin:0; font-size:38px; font-weight:bold; color:#3498db; margin-top:5px;">{g_total}</p></div>', unsafe_allow_html=True)
    
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, col_gap, c2 = st.columns([1, 0.1, 1])
    with c1:
        st.markdown('<p style="font-size:24px; font-weight:bold; margin-bottom:20px;">Sentimiento Global</p>', unsafe_allow_html=True)
        if g_total > 0:
            fig, ax = plt.subplots(figsize=(6, 5), facecolor='#0e1117')
            ax.set_facecolor('#0e1117')
            wedges, texts, autotexts = ax.pie([g_pos, g_neu, g_neg], labels=['Positivo', 'Neutro', 'Negativo'], autopct='%1.0f%%', startangle=90, colors=['#2ecc71', '#95a5a6', '#e74c3c'], textprops=dict(color="w", size=12), pctdistance=0.7)
            plt.setp(autotexts, size=12, weight="bold")
            centre_circle = plt.Circle((0,0),0.55,fc='#0e1117')
            fig.gca().add_artist(centre_circle)
            st.pyplot(fig)
    with c2:
        st.markdown('<p style="font-size:24px; font-weight:bold; margin-bottom:20px;">Volumen por Plataforma</p>', unsafe_allow_html=True)
        if distribucion_redes:
            fig, ax = plt.subplots(figsize=(6, 5), facecolor='#0e1117')
            ax.set_facecolor('#0e1117')
            ax.pie(list(distribucion_redes.values()), labels=list(distribucion_redes.keys()), startangle=90, colors=['#ff4b4b', '#45b7d1', '#7851a9', '#ff851b'], textprops=dict(color="w", size=12))
            centre_circle = plt.Circle((0,0),0.55,fc='#0e1117')
            fig.gca().add_artist(centre_circle)
            st.pyplot(fig)

# MÓDULO 4: POR PLATAFORMA
elif modulo_activo == "📈 Por Plataforma":
    st.markdown('<p style="font-size: 38px; font-weight: bold; margin-bottom:0px; letter-spacing:-0.5px;">Análisis Comparativo por Canal</p>', unsafe_allow_html=True)
    datos_sentimientos = []
    for nombre, archivo in redes_reporte:
        stats = parse_report_counts(archivo, nombre)
        if stats: datos_sentimientos.append((nombre, stats))
        
    if datos_sentimientos:
        fig, ax = plt.subplots(figsize=(14, 5), facecolor='#0e1117')
        ax.set_facecolor('#0e1117')
        
        plataformas = [d[0] for d in datos_sentimientos]
        positivos = [d[1].get("Positivo", 0) for d in datos_sentimientos]
        neutrales = [d[1].get("Neutral", 0) for d in datos_sentimientos]
        negativos = [d[1].get("Negativo", 0) for d in datos_sentimientos]
        
        # Base acumulada para apilar las barras correctamente
        bottom_neutral = positivos
        bottom_negativo = [p + n for p, n in zip(positivos, neutrales)]
        
        # Dibujar las 3 capas
        ax.bar(plataformas, positivos, label='Positivo', color='#2ecc71', width=0.35)
        ax.bar(plataformas, neutrales, bottom=bottom_neutral, label='Neutro', color='#95a5a6', width=0.35)
        ax.bar(plataformas, negativos, bottom=bottom_negativo, label='Negativo', color='#e74c3c', width=0.35)
        
        ax.tick_params(colors='w', labelsize=12)
        ax.legend(facecolor='#1e293b', edgecolor='none', labelcolor='white')
        st.pyplot(fig)
# MÓDULO 5: STORYTELLING AI
elif modulo_activo == "🤖 Storytelling AI":
    st.markdown('<div style="display: flex; align-items: center; margin-bottom: 35px; gap: 20px;"><div style="background-color: #1e293b; padding: 15px; border-radius: 12px;"><p style="font-size: 40px; margin: 0; line-height: 1;">🤖</p></div><div><p style="font-size: 38px; font-weight: bold; margin: 0; letter-spacing: -0.5px;">Informe Narrativo de IA Contextual</p></div></div>', unsafe_allow_html=True)
    archivo_premium = "reporte_storytelling_premium.md"
    if os.path.exists(archivo_premium):
        with open(archivo_premium, "r", encoding="utf-8") as f: contenido_md = f.read()
        st.markdown('<div style="background-color: #111622; padding: 45px; border-radius: 12px; border: 1px solid #2d3748;">', unsafe_allow_html=True)
        st.markdown(contenido_md)
        st.markdown('</div>', unsafe_allow_html=True)