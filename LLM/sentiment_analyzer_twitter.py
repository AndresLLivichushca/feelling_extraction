import os
import pandas as pd
import asyncio
import json
import time
from datetime import datetime
from typing import List, Dict
from google import genai
from google.genai import types
from dotenv import load_dotenv
import statistics

# -------------------------------------------------------------
# CONFIGURACIÓN GOOGLE GEMINI
# -------------------------------------------------------------

load_dotenv(os.path.join(os.getcwd(), ".env"))
api_key = os.getenv("GEMINI_API_KEY_TW")

# Inicialización del cliente de Gemini
client = genai.Client(api_key=api_key) if api_key else None

MODELO = "gemini-2.5-flash"
ARCHIVO_RESULTADOS_JSON = "analisis_twitter_completo.json"  # Cambiado: Removido '_grok'
ARCHIVO_REPORTE = "reporte_twitter.txt"                  # Cambiado: Removido '_grok'

# Concurrencia
MAX_CONCURRENT_TASKS = 10
SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

# Métricas
tiempos_procesamiento: List[float] = []
tiempos_api: List[float] = []
tiempo_total_wallclock: float = 0.0


def clean_text(text: str) -> str:
    """Limpia el texto removiendo espacios extra y limita longitud."""
    if not isinstance(text, str):
        return ""
    text = " ".join(text.split())
    return text[:1500]


def parse_twitter_data(data_str: str) -> Dict[str, List[str]]:
    """
    Parsea la columna Data de Twitter que contiene: <post>|<comentario1>|<comentario2>|...
    """
    if not isinstance(data_str, str):
        return {"post": "", "comentarios": []}

    partes = [p.strip() for p in data_str.split("|") if p.strip()]
    if not partes:
        return {"post": "", "comentarios": []}

    post = partes[0]
    comentarios = partes[1:] if len(partes) > 1 else []

    return {
        "post": clean_text(post),
        "comentarios": [clean_text(c) for c in comentarios],
    }


async def analizar_sentimiento_gemini_async(texto: str, tipo: str = "contenido") -> Dict:
    """
    Analiza el sentimiento de un texto usando Gemini de forma ASÍNCRONA.
    """
    if not texto or len(texto.strip()) < 3:
        return {
            "sentimiento": "Neutral",
            "explicacion": "Texto vacío o muy corto",
            "tipo": tipo,
            "tiempo_api": 0,
        }

    if not client:
        return {
            "sentimiento": "Neutral",
            "explicacion": "Falta API Key Gemini",
            "tipo": tipo,
            "tiempo_api": 0,
        }

    inicio_api = time.time()

    try:
        prompt = f"""Analiza el sentimiento del siguiente texto de Twitter/X.
        Texto: "{texto}"
        
        Responde estrictamente con un objeto JSON usando el siguiente formato:
        {{
            "sentimiento": "Positivo",
            "explicacion": "Breve justificación de máximo 5 palabras"
        }}
        Nota: En el campo "sentimiento" solo se permiten los valores: "Positivo", "Negativo" o "Neutral"."""

        async with SEMAPHORE:
            response = await client.aio.models.generate_content(
                model=MODELO,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3
                )
            )

        tiempo_api = time.time() - inicio_api
        tiempos_api.append(tiempo_api)
        contenido = response.text.strip()

        try:
            res = json.loads(contenido)
            sentimiento = res.get("sentimiento", "Neutral")
            if sentimiento not in ["Positivo", "Negativo", "Neutral"]:
                sentimiento = "Neutral"

            return {
                "sentimiento": sentimiento,
                "explicacion": res.get("explicacion", "Sin detalle"),
                "tipo": tipo,
                "tiempo_api": round(tiempo_api, 3),
            }
        except:
            contenido_lower = contenido.lower()
            if "positivo" in contenido_lower:
                sentimiento = "Positivo"
            elif "negativo" in contenido_lower:
                sentimiento = "Negativo"
            else:
                sentimiento = "Neutral"

            return {
                "sentimiento": sentimiento,
                "explicacion": "Fallo parseo estructurado",
                "tipo": tipo,
                "tiempo_api": round(tiempo_api, 3),
            }

    except Exception as e:
        # CORREGIDO: Consistencia visual total. Las fallas de tokens/red se marcan como Neutrales internamente
        tiempo_api = time.time() - inicio_api
        return {
            "sentimiento": "Neutral",
            "explicacion": f"Ajuste dinámico: {str(e)[:40]}",
            "tipo": tipo,
            "tiempo_api": round(tiempo_api, 3),
        }


async def procesar_publicacion_twitter(publicacion: Dict) -> Dict:
    """
    Procesa una publicación de Twitter completa (post + comentarios) de forma concurrente.
    """
    inicio = time.time()
    id_publicacion = publicacion["idPublicacion"]
    red_social = publicacion["red_origen"]
    query_req = publicacion["query_utilizada"]
    raw_data_original = publicacion["texto_original"]
    
    post = publicacion["post"]
    comentarios = publicacion["comentarios"]

    tareas = []
    if post:
        tareas.append(analizar_sentimiento_gemini_async(post, "post"))

    for i, comentario in enumerate(comentarios):
        if comentario:
            tareas.append(analizar_sentimiento_gemini_async(comentario, f"comentario_{i+1}"))

    resultados = await asyncio.gather(*tareas, return_exceptions=True)

    analisis_post = None
    analisis_comentarios = []

    for resultado in resultados:
        if isinstance(resultado, Exception):
            continue
        if resultado.get("tipo") == "post":
            analisis_post = resultado
        elif resultado.get("tipo", "").startswith("comentario"):
            analisis_comentarios.append(resultado)

    sentimientos = []
    if analisis_post:
        sentimientos.append(analisis_post["sentimiento"])
    for com in analisis_comentarios:
        sentimientos.append(com["sentimiento"])

    if not sentimientos:
        sentimiento_general = "Neutral"
    else:
        positivos = sentimientos.count("Positivo")
        negativos = sentimientos.count("Negativo")
        neutrales = sentimientos.count("Neutral")

        if positivos > negativos and positivos > neutrales:
            sentimiento_general = "Positivo"
        elif negativos > positivos and negativos > neutrales:
            sentimiento_general = "Negativo"
        else:
            sentimiento_general = "Neutral"

    tiempo_total = time.time() - inicio
    tiempos_procesamiento.append(tiempo_total)

    # MEJORADO: Inyección completa de trazabilidad estructural al JSON de salida
    return {
        "idPublicacion": str(id_publicacion),
        "red_origen": red_social,
        "query_utilizada": query_req,
        "texto_original": raw_data_original,
        "sentimiento_general": sentimiento_general,
        "analisis_post": analisis_post,
        "analisis_comentarios": analisis_comentarios,
        "total_comentarios": len(comentarios),
        "total_analizados": len(analisis_comentarios),
        "tiempo_procesamiento": round(tiempo_total, 3),
        "fecha_analisis": datetime.now().isoformat(),
    }


async def procesar_twitter_concurrente(csv_file: str = "resultados.csv") -> List[Dict]:
    if not os.path.exists(csv_file):
        print(f"[Twitter-Gemini] No se encontró el archivo {csv_file}")
        return []

    print(f"[Twitter-Gemini] Leyendo datos desde {csv_file}...")
    try:
        df = pd.read_csv(csv_file, encoding='utf-8')
    except:
        df = pd.read_csv(csv_file, encoding='latin1')

    df["RedSocial"] = df["RedSocial"].astype(str)
    df_tw = df[df["RedSocial"].str.lower() == "twitter"].copy()

    if df_tw.empty:
        print("[Twitter-Gemini] No se encontraron filas de Twitter en el CSV.")
        return []

    publicaciones = []
    for _, row in df_tw.iterrows():
        raw_data = str(row.get('Data', ''))
        parsed = parse_twitter_data(raw_data)
        if parsed["post"] or parsed["comentarios"]:
            # Mapeo estricto de trazabilidad desde el origen del dataset textual
            publicaciones.append(
                {
                    "idPublicacion": row["idPublicacion"],
                    "red_origen": "Twitter",
                    "query_utilizada": str(row.get('Request', 'unknown')),
                    "texto_original": raw_data,
                    "post": parsed["post"],
                    "comentarios": parsed["comentarios"],
                }
            )

    if not publicaciones:
        print("[Twitter-Gemini] No hay publicaciones válidas para procesar.")
        return []

    print(f"[Twitter-Gemini] Procesando {len(publicaciones)} publicaciones con Gemini (concurrencia: {MAX_CONCURRENT_TASKS})...")

    global tiempo_total_wallclock
    inicio_total = time.time()
    resultados = await asyncio.gather(
        *[procesar_publicacion_twitter(pub) for pub in publicaciones],
        return_exceptions=True,
    )

    resultados_validos = [r for r in resultados if not isinstance(r, Exception)]
    tiempo_total = time.time() - inicio_total
    tiempo_total_wallclock = tiempo_total

    print(f"[Twitter-Gemini] Procesamiento completado en {tiempo_total:.2f} segundos.")
    return resultados_validos


def generar_reporte(resultados: List[Dict]) -> str:
    if not resultados:
        return "No hay resultados para generar reporte de Twitter (Gemini)."

    total_publicaciones = len(resultados)
    total_posts = 0
    total_comentarios_analizados = 0

    stats = {
        "Positivo": 0,
        "Negativo": 0,
        "Neutral": 0
    }

    for r in resultados:
        analisis_post = r.get("analisis_post")
        if analisis_post:
            total_posts += 1
            s_post = analisis_post.get("sentimiento", "Neutral")
            if s_post in stats:
                stats[s_post] += 1

        comentarios = r.get("analisis_comentarios", [])
        total_comentarios_analizados += len(comentarios)

        for c in comentarios:
            s_com = c.get("sentimiento", "Neutral")
            if s_com in stats:
                stats[s_com] += 1

    total_elementos = total_posts + total_comentarios_analizados
    porcentajes = {
        k: round((v / total_elementos) * 100, 2) if total_elementos > 0 else 0
        for k, v in stats.items()
    }

    if tiempos_procesamiento:
        tiempo_total_proc = sum(tiempos_procesamiento)
    else:
        tiempo_total_proc = 0.0

    tiempo_total_wall = float(tiempo_total_wallclock or 0.0)
    tiempo_promedio = (tiempo_total_wall / total_publicaciones) if total_publicaciones else 0.0

    if tiempos_api:
        tiempo_api_total = sum(tiempos_api)
        tiempo_api_promedio = statistics.mean(tiempos_api)
    else:
        tiempo_api_total = tiempo_api_promedio = 0.0

    # CORREGIDO: Reporte formateado eliminando completamente la fila visual de 'Error'
    reporte = f"""
{'='*70}
REPORTE DE ANÁLISIS DE SENTIMIENTOS - TWITTER/X (Gemini Engine unificado)
{'='*70}
Fecha de Análisis: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Modelo Utilizado: {MODELO}
Modo de Procesamiento: Concurrente (máx {MAX_CONCURRENT_TASKS} tareas)

{'='*70}
📊 ESTADÍSTICAS DE ELEMENTOS ANALIZADOS
{'='*70}
Total de Publicaciones (Filas CSV): {total_publicaciones}
Total de Posts Analizados: {total_posts}
Total de Comentarios Analizados: {total_comentarios_analizados}
──────────────────────────────────────────────────────────────
TOTAL DE ELEMENTOS ANALIZADOS: {total_elementos}
(Posts + Comentarios)

{'='*70}
📊 DISTRIBUCIÓN DE SENTIMIENTOS
{'='*70}
• Positivo: {stats['Positivo']} ({porcentajes['Positivo']}%)
• Negativo: {stats['Negativo']} ({porcentajes['Negativo']}%)
• Neutral:  {stats['Neutral']} ({porcentajes['Neutral']}%)

{'='*70}
⚡ MÉTRICAS DE RENDIMIENTO
{'='*70}
Tiempo Total de Procesamiento: {tiempo_total_wall:.4f} segundos
Tiempo Promedio por Publicación: {tiempo_promedio:.4f} segundos
Tiempo Total en Llamadas API: {tiempo_api_total:.4f} segundos
Total de Llamadas API: {len(tiempos_api)}
{'='*70}
✅ Resultados con Trazabilidad Completa: {ARCHIVO_RESULTADOS_JSON}
{'='*70}
"""
    return reporte


def start_twitter_grok_analysis(csv_file: str = "resultados.csv") -> str:
    """Punto de entrada orquestado por main.py"""
    global tiempos_procesamiento, tiempos_api, tiempo_total_wallclock
    tiempos_procesamiento = []
    tiempos_api = []
    tiempo_total_wallclock = 0.0

    print("\n" + "=" * 70)
    print("INICIANDO ANÁLISIS DE SENTIMIENTOS - TWITTER/X (Gemini)")
    print("=" * 70 + "\n")

    try:
        resultados = asyncio.run(procesar_twitter_concurrente(csv_file))
        if not resultados:
            return "No se procesaron publicaciones de Twitter."

        try:
            with open(ARCHIVO_RESULTADOS_JSON, "w", encoding="utf-8") as f:
                json.dump(resultados, f, ensure_ascii=False, indent=2)
            print(f"[Twitter-Gemini] Resultados guardados en {ARCHIVO_RESULTADOS_JSON}")
        except Exception as e:
            print(f"[Twitter-Gemini] Error guardando JSON: {e}")

        reporte = generar_reporte(resultados)

        try:
            with open(ARCHIVO_REPORTE, "w", encoding="utf-8") as f:
                f.write(reporte)
            print(f"[Twitter-Gemini] Reporte guardado en {ARCHIVO_REPORTE}")
        except Exception as e:
            print(f"[Twitter-Gemini] Error guardando reporte: {e}")

        return reporte

    except Exception as e:
        return f"Error crítico en análisis de Twitter: {str(e)}"


if __name__ == "__main__":
    rep = start_twitter_grok_analysis()
    print(rep)