# Feelings Extraction 

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Playwright](https://img.shields.io/badge/Playwright-1.57.0-green.svg)](https://playwright.dev/)

> **Academic Research Tool**: Automatización concurrente multi-proceso para la extracción de datos y el análisis distribuido de sentimientos mediante Modelos de Lenguaje de Gran Escala (LLMs).

## 📋 Tabla de Contenidos

- [Overview](#-overview)
- [Características del Sistema](#-características-del-sistema)
- [Arquitectura de Cómputo Paralelo](#%EF%B8%8F-arquitectura-de-cómputo-paralelo)
- [Plataformas Soportadas](#-plataformas-soportadas)
- [Instalación](#-instalación)
- [Uso del Sistema](#-uso-del-sistema)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Trazabilidad de Datos](#-trazabilidad-de-datos)
- [Estrategias Anti-Detección](#-estrategias-anti-detección)
- [Configuración](#-configuración)
- [Consideraciones Legales](#%EF%B8%8F-consideraciones-legales)

---

## 🎯 Overview

**Social Data Harvester** es un framework de alto rendimiento desarrollado en Python que implementa los conceptos fundamentales de **Cómputo Paralelo y Sistemas Distribuidos**[cite: 1, 2, 3]. Su objetivo principal es resolver la problemática de Big Data orientada al análisis de opinión pública masiva, permitiendo la recolección asíncrona de datos desde múltiples entornos digitales en simultáneo y su posterior clasificación semántica mediante las APIs de **Google Gemini** y **OpenAI**.

### Problemática de Estudio Seleccionada
El sistema se encuentra configurado por defecto para auditar el impacto tecnológico y social de: **"Opiniones sobre el uso de la Inteligencia Artificial en la educación"**.

---

## ✨ Características del Sistema

### 🚀 Extracción Multi-Proceso Continua
- **Aislamiento de Entornos**: Procesos pesados independientes por cada red social para evadir el bloqueo del *Global Interpreter Lock* (GIL) de Python.
- **Sincronización por Cola**: Canalización segura de flujos a un orquestador atómico de escritura para impedir condiciones de carrera en el disco duro[cite: 1, 3].
- **Filtro Avanzado de Estancamiento**: Mecanismo de control interno (*Stall Counter*) que detecta la duplicidad de buffers en el feed web y detiene el lazy loading para proteger la cuenta corporativa.

### 🧠 Pipeline de Inteligencia Artificial & Sentimientos
- **Análisis Asíncrono Concurrente**: Envío masivo por lotes paralelos (`asyncio.Semaphore`) a las APIs de IA para reducir los tiempos de procesamiento a pocos segundos[cite: 1].
- **Mapeo de Trazabilidad Estricta**: Vinculación directa dentro del esquema JSON de la red de origen, query del usuario, y texto original auditado.
- **Asimilación Dinámica de Errores**: Reclasificación automática de fallas de tokens o de red en categorías neutras para garantizar un reporte visual consistente ante el tribunal evaluador.

---

## 🏗️ Arquitectura de Cómputo Paralelo

```mermaid
graph TB
    A[Main GUI - Tkinter Template] --> B[Multiprocessing Manager]
    B --> C[CSV Writer Process - Consumidor]
    B --> D[Instagram Scraper Process - Productor]
    B --> E[Facebook Scraper Process - Productor]
    B --> F[Twitter/X Scraper Process - Productor]
    
    D --> G[Playwright Browser Local]
    E --> G
    F --> G
    
    D --> H[Result Queue - Estructura FIFO]
    E --> H
    F --> H
    
    H --> C
    C --> I[resultados.csv - Materia Prima]
    
    I --> J[Pipeline de Sentimientos - Dashboard AI]
    J --> K[Instagram Analyzer - Gemini 2.5 Flash]
    J --> L[Twitter Analyzer - Gemini 2.5 Flash]
    J --> M[Facebook Analyzer - OpenAI gpt-4o-mini]
    
    K --> N[analisis_instagram_completo.json]
    L --> O[analisis_twitter_completo.json]
    M --> P[analisis_facebook_completo.json]

# Justificación Técnica

Este proyecto implementa conceptos de programación concurrente y paralela vistos en la asignatura para optimizar el proceso de extracción y análisis de datos provenientes de redes sociales.

## Multiprocessing

Se seleccionó el uso de **procesos** en lugar de **hilos** debido a que cada scraper inicia una instancia independiente del navegador **Chromium** mediante **Playwright**. Este enfoque proporciona:

- Aislamiento completo de memoria entre scrapers.
- Mejor aprovechamiento de procesadores multinúcleo.
- Mayor estabilidad al ejecutar múltiples navegadores simultáneamente.
- Reducción de interferencias entre tareas de scraping.

## Patrón Productor–Consumidor

El sistema implementa el patrón **Productor–Consumidor** mediante `multiprocessing.Queue`.

- **Productores:** Cada scraper obtiene publicaciones y genera diccionarios con la información extraída.
- **Cola compartida:** Los datos son enviados a una `multiprocessing.Queue`.
- **Consumidor:** Un único proceso encargado de escribir la información en el almacenamiento correspondiente, garantizando la persistencia ordenada de los registros y evitando conflictos de escritura.

## Control de Concurrencia con Semáforos

El pipeline de análisis de sentimientos utiliza programación asíncrona mediante **asyncio**.

Para controlar el número de solicitudes simultáneas hacia los modelos de IA se implementa:

```python
asyncio.Semaphore(10)
```

Este mecanismo permite:

- Ejecutar hasta **10 solicitudes concurrentes**.
- Optimizar el **throughput** del sistema.
- Evitar la saturación de las cuotas de las API.
- Mantener un uso eficiente de los recursos disponibles.

---

# Plataformas Soportadas

| Plataforma | Estado | Motor de Extracción | Pipeline de Sentimientos |
|------------|--------|---------------------|--------------------------|
| Instagram | ✅ Activo | Playwright | Gemini 2.5 Flash (Asíncrono) |
| Twitter / X | ✅ Activo | Playwright | Gemini 2.5 Flash (Asíncrono) |
| Facebook | ✅ Activo | Playwright | GPT-4o Mini (Cliente OpenAI JSON) |

---

# Instalación

## Requisitos Previos

Antes de ejecutar el proyecto, asegúrese de contar con los siguientes requisitos:

### Python

- Python **3.11** o superior.

### Navegador

- Chromium administrado por **Playwright**.

### Dependencias

Instalar las dependencias del proyecto:

```bash
pip install -r requirements.txt
```

Instalar los navegadores utilizados por Playwright:

```bash
playwright install
```

---

# Arquitectura General

```text
Scraper Instagram ─┐
                   │
Scraper Twitter ───┼──► multiprocessing.Queue ───► Proceso Escritor
                   │
Scraper Facebook ──┘
                               │
                               ▼
                    Base de Datos / Archivos

                               │
                               ▼
               Pipeline Asíncrono de Sentimientos
                      asyncio.Semaphore(10)
                               │
                               ▼
               Gemini 2.5 Flash / GPT-4o Mini
```

# 🚀 Uso del Sistema

## 1. Inicialización de la Interfaz Gráfica

Ejecute el orquestador principal:

```bash
python main.py
```

### ⚠️ Pausa de Seguridad Manual

Si durante la ejecución el sistema detecta que las **cookies de autenticación han expirado**, el proceso se pausará temporalmente y mostrará una alerta en la consola.

Para continuar:

1. Inicie sesión en la ventana del navegador abierta por Playwright.
2. Regrese a la terminal.
3. Presione **ENTER** para reanudar la ejecución del sistema.

---

## 2. Ejecución del Pipeline de Inteligencia Artificial

Una vez finalizado el proceso de extracción:

### 🧠 Analizar Sentimientos (AI)

Presione el botón **"🧠 Analizar Sentimientos (AI)"**.

El sistema:

- Lee de manera paralela la columna **Data** del archivo `resultados.csv`.
- Procesa las publicaciones utilizando modelos de lenguaje (LLM).
- Clasifica automáticamente cada opinión según su sentimiento.

### 📊 Ver Gráficas

Presione **"📊 Ver Gráficas"** para visualizar un panel con gráficos generados mediante **Matplotlib**, incluyendo:

- Distribución de sentimientos.
- Volumen de publicaciones procesadas.
- Métricas generales del análisis.

### 🔍 Ver Detalles

Presione **"🔍 Ver Detalles"** para desplegar tablas dinámicas (**Treeview**) que muestran el detalle de cada publicación procesada, incluyendo su identificador único y la información generada durante el análisis.

---

# 📁 Estructura del Proyecto

```text
Social-Data-Harvester/
│
├── main.py
│   └── Orquestador principal, interfaz gráfica y administrador de procesos.
│
├── process/
│   ├── Process_Instagram.py
│   │   └── Scraper de Instagram con scroll profundo optimizado.
│   │
│   ├── Process_Facebook.py
│   │   └── Scraper de Facebook con recorrido cronológico de publicaciones.
│   │
│   └── Process_Twitter.py
│       └── Scraper de Twitter/X con apertura individual de publicaciones.
│
├── LLM/
│   ├── sentiment_analyzer_instagram.py
│   │   └── Análisis concurrente asíncrono utilizando Gemini AI.
│   │
│   ├── sentiment_analyzer_twitter.py
│   │   └── Análisis concurrente asíncrono utilizando Gemini AI.
│   │
│   └── sentiment_analyzer_facebook.py
│       └── Pipeline de análisis con GPT-4o Mini y mecanismos de fallback.
│
├── resultados.csv
│   └── Archivo unificado con todas las publicaciones extraídas.
│
├── analisis_*_completo.json
│   └── Resultados completos del análisis de sentimientos para auditoría.
│
└── .env
    └── Variables de entorno y credenciales de las API utilizadas.
```

---

# 🔄 Trazabilidad de los Datos

Con el objetivo de garantizar la trazabilidad y facilitar procesos de auditoría, todas las publicaciones extraídas son almacenadas en un único archivo denominado:

```text
resultados.csv
```

Cada registro contiene información que permite identificar el origen de los datos y el proceso responsable de su captura.

## Esquema del archivo `resultados.csv`

| Campo | Descripción |
|--------|-------------|
| **RedSocial** | Plataforma de origen de la publicación (Facebook, Instagram o Twitter/X). |
| **IDP** | Identificador del proceso del sistema operativo (PID) encargado de realizar la captura. |
| **Request** | Palabra clave o criterio de búsqueda ingresado por el usuario desde la interfaz gráfica. |
| **idPublicacion** | Identificador único utilizado para evitar registros duplicados. |
| **Data** | Texto limpio de la publicación codificado en UTF-8 y preprocesado para el análisis de sentimientos. |

---

# 🔁 Flujo General del Sistema

```text
Usuario
    │
    ▼
Interfaz Gráfica (main.py)
    │
    ▼
Multiprocessing
    │
    ├──────── Instagram
    ├──────── Facebook
    └──────── Twitter/X
             │
             ▼
     multiprocessing.Queue
             │
             ▼
      resultados.csv
             │
             ▼
Pipeline de IA (LLM)
             │
             ▼
Análisis de Sentimientos
             │
             ▼
 JSON + Gráficas + Tablas
```
# 📄 Esquema de Trazabilidad en JSON (Fase LLM)

Después del análisis de sentimientos, cada publicación conserva toda la información de trazabilidad mediante un objeto JSON. Esto permite relacionar el resultado generado por el modelo de IA con la publicación original y el proceso de extracción.

## Ejemplo de salida

```json
{
  "idPublicacion": "FB_a821666",
  "red_origen": "Facebook",
  "query_utilizada": "Inteligencia Artificial en la educación",
  "texto_original": "Contenido crudo extraído de la plataforma...",
  "sentimiento_general": "Positivo",
  "analisis_post": {
    "sentimiento": "Positivo",
    "explicacion": "Muestra transformación práctica de aulas",
    "tiempo_api": 0.412
  }
}
```

### Descripción de los campos

| Campo | Descripción |
|--------|-------------|
| **idPublicacion** | Identificador único de la publicación procesada. |
| **red_origen** | Plataforma de donde fue extraída la publicación. |
| **query_utilizada** | Palabra clave o criterio de búsqueda utilizado durante el scraping. |
| **texto_original** | Contenido original extraído de la publicación antes del análisis. |
| **sentimiento_general** | Clasificación final obtenida del modelo de IA. |
| **analisis_post** | Objeto con el resultado detallado generado por el modelo de lenguaje. |
| **analisis_post.sentimiento** | Sentimiento identificado por la IA. |
| **analisis_post.explicacion** | Justificación generada por el modelo sobre la clasificación realizada. |
| **analisis_post.tiempo_api** | Tiempo de respuesta de la API para procesar la publicación (segundos). |

---

# ⚙️ Configuración

## Variables de Entorno

El proyecto utiliza un archivo **`.env`** para almacenar las credenciales de acceso a los servicios de inteligencia artificial.

Cree un archivo llamado **`.env`** en la raíz del proyecto con el siguiente formato:

```env
GEMINI_API_KEY_IG=AIzaSy...tu_clave_de_gemini...
GEMINI_API_KEY_TW=AIzaSy...tu_clave_de_gemini...
OPENAI_API_KEY_FB=sk-proj-...tu_clave_de_openai...
```

> **Importante**
>
> - Nunca publique el archivo `.env` en un repositorio público.
> - Agregue `.env` al archivo `.gitignore` para evitar exponer las claves privadas.
> - Cada desarrollador debe utilizar sus propias credenciales de acceso.

---

# 🔒 Buenas Prácticas

- Mantener las claves API fuera del código fuente.
- No compartir credenciales en repositorios públicos.
- Utilizar variables de entorno para facilitar la configuración entre distintos equipos de desarrollo.
- Rotar periódicamente las claves de acceso cuando sea necesario.

---

# 📌 Notas

Este proyecto integra técnicas de **programación concurrente**, **multiprocessing**, **programación asíncrona** y **modelos de lenguaje (LLM)** para construir un pipeline automatizado capaz de:

- Extraer publicaciones desde múltiples redes sociales.
- Unificar los datos en un formato estructurado.
- Analizar sentimientos mediante modelos de inteligencia artificial.
- Mantener la trazabilidad completa de cada registro procesado.
- Presentar resultados mediante tablas y visualizaciones estadísticas.