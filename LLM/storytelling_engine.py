import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.getcwd(), '.env'))

def generar_storytelling_global() -> str:
    """Lee todos los reportes de las redes y genera un informe ejecutivo narrativo continuo"""
    api_key = os.getenv("OPENAI_API_KEY_STORYTELLING")
    if not api_key:
        return "⚠️ Error: OPENAI_API_KEY_STORYTELLING no configurada en el entorno."

    client = OpenAI(api_key=api_key)
    
    # Recopilar la información de los reportes existentes para pasarla como contexto
    archivos = {
        "Facebook": "reporte_facebook_openai.txt",
        "Instagram": "reporte_instagram_openai.txt",
        "YouTube": "reporte_youtube.txt",
        "Reddit": "reporte_reddit.txt"
    }
    
    contexto_reportes = ""
    for red, archivo in archivos.items():
        if os.path.exists(archivo):
            with open(archivo, "r", encoding="utf-8") as f:
                contexto_reportes += f"\n--- DATOS CRUDOS DE {red.upper()} ---\n" + f.read()

    if not contexto_reportes.strip():
        return "Aún no hay datos analizados en las plataformas para construir el informe interpretativo."

    prompt = f"""Actúa como un Director de Operaciones y Analista de Opinión Pública Senior. 
    A continuación te proporciono los reportes de análisis de sentimiento crudos obtenidos de nuestro pipeline paralelo:
    
    {contexto_reportes}
    
    Basándote en esos datos cuantitativos reales, genera un 'Informe Narrativo AI' continuo y formal.
    Usa un lenguaje corporativo, analítico y elegante. Estructura la respuesta usando estrictamente los siguientes tres puntos:

    1. Resumen Global: Un Paisaje de Opinión Predominante
    (Redacta un párrafo analítico que describa la tendencia general del ecosistema, mencionando porcentajes consolidados globales y qué significa esta percepción pública).

    2. Análisis Comparativo por Plataforma: Audiencias y Dinámicas
    (Analiza cómo se comportó cada red social. Contrasta por qué una red es más positiva o negativa que otra según los datos, y cómo influye la maquetación de cada comunidad).

    3. Insights Cualitativos y Conclusiones Estratégicas
    (Brinda conclusiones de alto nivel basados en el volumen total analizado y qué acciones o patrones de fricción se detectaron en los debates).

    REGLA: Devuelve el texto directamente formateado en Markdown limpio, usa títulos llamativos para los puntos y resalta conceptos clave en negrita. No agregues saludos ni introducciones genéricas."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un experto en Business Intelligence y Storytelling de Datos. Redactas informes ejecutivos de alto nivel."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=900
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error al generar el Storytelling con la API dedicada: {str(e)}"