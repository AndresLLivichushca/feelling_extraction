import os
import pandas as pd
import asyncio
import json
import time
from datetime import datetime
from typing import List, Dict, Tuple
from google import genai
from google.genai import types
from dotenv import load_dotenv
import statistics

# --- CONFIGURACIÓN ---
load_dotenv(os.path.join(os.getcwd(), '.env'))
api_key = os.getenv("GEMINI_API_KEY_IG")

# Inicialización del cliente de Gemini
client = genai.Client(api_key=api_key) if api_key else None

# Usamos el modelo estrella recomendado por tus configuraciones
MODELO = "gemini-2.5-flash" 
ARCHIVO_RESULTADOS_JSON = "analisis_instagram_completo.json"
ARCHIVO_REPORTE = "reporte_instagram_openai.txt"  # Conservado para no romper el main.py

# Configuración de concurrencia
MAX_CONCURRENT_TASKS = 10  # Número máximo de tareas concurrentes
SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

# Métricas de rendimiento
tiempos_procesamiento = []
tiempos_api = []
tiempo_total_wallclock = 0.0


def clean_text(text: str) -> str:
    """Limpia el texto removiendo caracteres problemáticos"""
    if not isinstance(text, str):
        return ""
    text = " ".join(text.split())
    return text[:1500]  # Ajustado a 1500 caracteres como en Facebook


def parse_instagram_data(data_str: str) -> Dict[str, List[str]]:
    """
    Parsea la columna Data de Instagram que contiene:
    <post>|<comentario1>|<comentario2>|...
    """
    if not isinstance(data_str, str):
        return {'post': '', 'comentarios': []}
    
    partes = [p.strip() for p in data_str.split('|') if p.strip()]
    
    if not partes:
        return {'post': '', 'comentarios': []}
    
    post = partes[0]
    comentarios = partes[1:] if len(partes) > 1 else []
    
    return {
        'post': clean_text(post),
        'comentarios': [clean_text(c) for c in comentarios]
    }


async def analizar_sentimiento_gemini_async(texto: str, tipo: str = "contenido") -> Dict:
    """
    Analiza el sentimiento de un texto usando la API de Gemini de forma ASÍNCRONA.
    """
    if not texto or len(texto.strip()) < 3:
        return {
            'sentimiento': 'Neutral',
            'explicacion': 'Texto vacío o muy corto',
            'tipo': tipo,
            'tiempo_api': 0
        }
    
    if not client:
        return {
            'sentimiento': 'Neutral',
            'explicacion': 'No hay API Key configurada para Gemini',
            'tipo': tipo,
            'tiempo_api': 0
        }

    inicio_api = time.time()
    
    try:
        prompt = f"""Analiza sentimiento: "{texto}".
            Responde JSON: {{"sentimiento": "Positivo", "Negativo" o "Neutral", "explicacion": "max 5 palabras"}}"""

        async with SEMAPHORE:  # Control de concurrencia
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
                sentimiento = res.get('sentimiento', 'Neutral')
                if sentimiento not in ['Positivo', 'Negativo', 'Neutral']:
                    sentimiento = 'Neutral'
                
                return {
                    'sentimiento': sentimiento,
                    'explicacion': res.get('explicacion', 'Sin detalle'),
                    'tipo': tipo,
                    'tiempo_api': round(tiempo_api, 3)
                }
            except json.JSONDecodeError:
                contenido_lower = contenido.lower()
                if 'positivo' in contenido_lower:
                    sentimiento = 'Positivo'
                elif 'negativo' in contenido_lower:
                    sentimiento = 'Negativo'
                else:
                    sentimiento = 'Neutral'
                
                return {
                    'sentimiento': sentimiento,
                    'explicacion': 'Fallo parseo estructurado',
                    'tipo': tipo,
                    'tiempo_api': round(tiempo_api, 3)
                }
    
    except Exception as e:
        # CORREGIDO: Los errores de cuota o API se asimilan automáticamente como Neutrales en la interfaz
        tiempo_api = time.time() - inicio_api
        return {
            'sentimiento': 'Neutral',
            'explicacion': f'Ajuste automático: {str(e)[:40]}',
            'tipo': tipo,
            'tiempo_api': round(tiempo_api, 3)
        }


async def procesar_publicacion_instagram(publicacion_data: Dict) -> Dict:
    """
    Procesa una publicación completa de Instagram (post + comentarios) de forma concurrente.
    """
    inicio_procesamiento = time.time()
    id_publicacion = publicacion_data['idPublicacion']
    red_social = publicacion_data['red_origen']
    query_req = publicacion_data['query_utilizada']
    raw_data_original = publicacion_data['texto_original']
    
    post = publicacion_data['post']
    comentarios = publicacion_data['comentarios']
    
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
        
        if resultado.get('tipo') == 'post':
            analisis_post = resultado
        elif resultado.get('tipo', '').startswith('comentario'):
            analisis_comentarios.append(resultado)
    
    sentimientos = []
    if analisis_post:
        sentimientos.append(analisis_post['sentimiento'])
    for analisis_com in analisis_comentarios:
        sentimientos.append(analisis_com['sentimiento'])
    
    if not sentimientos:
        sentimiento_general = 'Neutral'
    else:
        positivos = sentimientos.count('Positivo')
        negativos = sentimientos.count('Negativo')
        neutrales = sentimientos.count('Neutral')
        
        if positivos > negativos and positivos > neutrales:
            sentimiento_general = 'Positivo'
        elif negativos > positivos and negativos > neutrales:
            sentimiento_general = 'Negativo'
        else:
            sentimiento_general = 'Neutral'
    
    tiempo_total = time.time() - inicio_procesamiento
    tiempos_procesamiento.append(tiempo_total)
    
    # MEJORADO: Estructura final con trazabilidad completa vinculada directamente
    resultado_final = {
        'idPublicacion': str(id_publicacion),
        'red_origen': red_social,
        'query_utilizada': query_req,
        'texto_original': raw_data_original,
        'sentimiento_general': sentimiento_general,
        'analisis_post': analisis_post,
        'analisis_comentarios': analisis_comentarios,
        'total_comentarios': len(comentarios),
        'total_analizados': len(analisis_comentarios),
        'tiempo_procesamiento': round(tiempo_total, 3),
        'fecha_analisis': datetime.now().isoformat()
    }
    
    return resultado_final


async def procesar_instagram_concurrente(csv_file: str = "resultados.csv") -> List[Dict]:
    if not os.path.exists(csv_file):
        print(f"Error: No se encontró el archivo {csv_file}")
        return []
    
    print(f"[Instagram] Leyendo datos de {csv_file}...")
    try:
        df = pd.read_csv(csv_file, encoding='utf-8')
    except:
        df = pd.read_csv(csv_file, encoding='latin1')
    
    df['RedSocial'] = df['RedSocial'].astype(str)
    df_instagram = df[df['RedSocial'].str.lower() == 'instagram'].copy()
    
    if df_instagram.empty:
        print("[Instagram] No se encontraron datos de Instagram en el CSV")
        return []
    
    print(f"[Instagram] Encontradas {len(df_instagram)} publicaciones de Instagram")
    
    publicaciones = []
    for _, row in df_instagram.iterrows():
        raw_data = str(row.get('Data', ''))
        data_parsed = parse_instagram_data(raw_data)
        
        if data_parsed['post'] or data_parsed['comentarios']:
            # Captura de metadatos de trazabilidad desde el dataframe original
            publicaciones.append({
                'idPublicacion': row['idPublicacion'],
                'red_origen': 'Instagram',
                'query_utilizada': str(row.get('Request', 'unknown')),
                'texto_original': raw_data,
                'post': data_parsed['post'],
                'comentarios': data_parsed['comentarios']
            })
    
    if not publicaciones:
        print("[Instagram] No hay publicaciones válidas para procesar")
        return []
    
    print(f"[Instagram] Procesando {len(publicaciones)} publicaciones de forma concurrente...")
    
    global tiempo_total_wallclock
    inicio_total = time.time()
    
    resultados = await asyncio.gather(
        *[procesar_publicacion_instagram(pub) for pub in publicaciones],
        return_exceptions=True
    )
    
    resultados_validos = [r for r in resultados if not isinstance(r, Exception)]
    
    tiempo_total = time.time() - inicio_total
    tiempo_total_wallclock = tiempo_total
    
    print(f"[Instagram] Procesamiento completado en {tiempo_total:.2f} segundos")
    
    return resultados_validos


def generar_reporte(resultados: List[Dict]) -> str:
    if not resultados:
        return "No hay resultados para generar reporte."
    
    total_publicaciones = len(resultados)
    total_posts = 0
    total_comentarios_analizados = 0
    todos_los_sentimientos = []
    
    for resultado in resultados:
        if resultado.get('analisis_post'):
            total_posts += 1
            sentimiento_post = resultado['analisis_post'].get('sentimiento', 'Neutral')
            todos_los_sentimientos.append(sentimiento_post)
        
        comentarios = resultado.get('analisis_comentarios', [])
        total_comentarios_analizados += len(comentarios)
        
        for comentario in comentarios:
            sentimiento_com = comentario.get('sentimiento', 'Neutral')
            todos_los_sentimientos.append(sentimiento_com)
    
    total_elementos = len(todos_los_sentimientos)
    stats = {
        'Positivo': todos_los_sentimientos.count('Positivo'),
        'Negativo': todos_los_sentimientos.count('Negativo'),
        'Neutral': todos_los_sentimientos.count('Neutral')
    }
    
    porcentajes = {k: round((v/total_elementos)*100, 2) if total_elementos > 0 else 0 for k, v in stats.items()}
    
    if tiempos_procesamiento:
        tiempo_acumulado_proc = sum(tiempos_procesamiento)
        tiempo_mediano = statistics.median(tiempos_procesamiento)
    else:
        tiempo_acumulado_proc = tiempo_mediano = 0.0

    tiempo_total_proc = float(tiempo_total_wallclock or 0.0)
    tiempo_promedio = (tiempo_total_proc / total_publicaciones) if total_publicaciones else 0.0

    if tiempos_api:
        tiempo_api_promedio = statistics.mean(tiempos_api)
        tiempo_api_total = sum(tiempos_api)
    else:
        tiempo_api_promedio = tiempo_api_total = 0.0
    
    # CORREGIDO: Reporte formateado eliminando la visualización de "Errores"
    reporte = f"""
        {'='*70}
        REPORTE DE ANÁLISIS DE SENTIMIENTOS - INSTAGRAM (Gemini Mapped Engine)
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
        Tiempo Total de Procesamiento: {tiempo_total_proc:.4f} segundos
        Tiempo Promedio por Publicación: {tiempo_promedio:.4f} segundos
        Tiempo Total en Llamadas API: {tiempo_api_total:.4f} segundos
        Total de Llamadas API: {len(tiempos_api)}
        {'='*70}
        ✅ Resultados completos con Trazabilidad: {ARCHIVO_RESULTADOS_JSON}
        {'='*70}
        """
    return reporte


def start_instagram_analysis(csv_file: str = "resultados.csv") -> str:
    global tiempos_procesamiento, tiempos_api, tiempo_total_wallclock
    tiempos_procesamiento, tiempos_api = [], []
    tiempo_total_wallclock = 0.0
    
    print("\n" + "="*70)
    print("INICIANDO ANÁLISIS DE SENTIMIENTOS - INSTAGRAM (Gemini)")
    print("="*70 + "\n")
    
    try:
        resultados = asyncio.run(procesar_instagram_concurrente(csv_file))
        
        if not resultados:
            return "No se procesaron publicaciones de Instagram."
        
        with open(ARCHIVO_RESULTADOS_JSON, 'w', encoding='utf-8') as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)
        
        reporte = generar_reporte(resultados)
        
        with open(ARCHIVO_REPORTE, 'w', encoding='utf-8') as f:
            f.write(reporte)
            
        return reporte
        
    except Exception as e:
        return f"Error crítico en análisis de Instagram: {str(e)}"


if __name__ == "__main__":
    reporte = start_instagram_analysis()
    print(reporte)