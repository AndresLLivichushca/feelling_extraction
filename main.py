import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
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
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


def clean_text(text):
    """Limpia el texto: remueve emojis y caracteres no UTF-8"""
    if not isinstance(text, str):
        return str(text)
    
    # Patrón para remover emojis y símbolos especiales
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # símbolos y pictogramas
        "\U0001F680-\U0001F6FF"  # transporte y mapas
        "\U0001F1E0-\U0001F1FF"  # banderas
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # símbolos encerrados
        "\U0001F900-\U0001F9FF"  # suplemento de emojis
        "\U0001FA00-\U0001FA6F"  # símbolos de ajedrez
        "\U0001FA70-\U0001FAFF"  # símbolos extendidos
        "\U00002600-\U000026FF"  # símbolos misceláneos
        "\U00002700-\U000027BF"  # dingbats
        "\U0001F004-\U0001F0CF"  # cartas de juego
        "]+", 
        flags=re.UNICODE
    )
    
    # Remover emojis
    text = emoji_pattern.sub('', text)
    
    # Asegurar UTF-8 válido (remover caracteres problemáticos)
    text = text.encode('utf-8', errors='ignore').decode('utf-8')
    
    # Limpiar espacios múltiples
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def csv_writer_process(result_queue, stop_event, filename="resultados.csv"):
    """Proceso dedicado para escribir en CSV (evita condición de carrera)"""
    fieldnames = ['RedSocial', 'IDP', 'Request', 'FechaPeticion', 
                  'FechaPublicacion', 'idPublicacion', 'Data']
    
    # Verificar si el archivo existe para decidir si escribir header
    file_exists = os.path.exists(filename) and os.path.getsize(filename) > 0
    
    # Modo 'a' para continuar agregando sin sobrescribir
    with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Solo escribir header si el archivo es nuevo o está vacío
        if not file_exists:
            writer.writeheader()
        
        while not stop_event.is_set() or not result_queue.empty():
            try:
                data = result_queue.get(timeout=1)
                # Limpiar todos los campos de texto (UTF-8 + sin emojis)
                cleaned_data = {
                    key: clean_text(value) if isinstance(value, str) else value
                    for key, value in data.items()
                }
                writer.writerow(cleaned_data)
                csvfile.flush()
            except queue.Empty:
                continue


def run_llm_process(network, result_queue):
    """
    Proceso paralelo para ejecutar los LLMs de cada red social.
    """
    try:
        if network == "Facebook":
            from LLM.sentiment_analyzer_facebook import start_facebook_analysis
            reporte = start_facebook_analysis("resultados.csv")
            result_queue.put((network, reporte))
            
        elif network == "Instagram":
            from LLM.sentiment_analyzer_instagram import start_instagram_analysis
            reporte = start_instagram_analysis("resultados.csv")
            result_queue.put((network, reporte))

        elif network == "Twitter":
            from LLM.sentiment_analyzer_twitter import start_twitter_grok_analysis
            reporte = start_twitter_grok_analysis("resultados.csv")
            result_queue.put((network, reporte))
            

    except Exception as e:
        result_queue.put((network, f"Error crítico en LLM {network}: {e}"))


class ScraperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Multi-Red Social Scraper (Gemini Edition)")
        self.root.geometry("850x650")
        self.root.configure(bg="#F3F4F6")  # Fondo general gris claro moderno
        
        self.processes = []
        self.result_queue = Queue()
        self.stop_event = Event()
        self.writer_process = None
        
        # Configurar Estilos Visuales Avanzados
        self.style = ttk.Style()
        self.style.theme_use("clam")  # Permite modificar colores nativos
        
        # Estilo para los LabelFrames
        self.style.configure("TLabelframe", background="#F3F4F6", bordercolor="#D1D5DB", thickness=1)
        self.style.configure("TLabelframe.Label", background="#F3F4F6", foreground="#1F2937", font=("Arial", 10, "bold"))
        
        # Estilo para las Etiquetas de texto
        self.style.configure("TLabel", background="#F3F4F6", foreground="#374151", font=("Arial", 9))
        self.style.configure("Status.TLabel", background="#E5E7EB", foreground="#111827", font=("Consolas", 10, "bold"))
        
        # Estilo para Botones Principales (Azul Tecnológico)
        self.style.configure("Primary.TButton", background="#2563EB", foreground="white", font=("Arial", 9, "bold"), borderwidth=0)
        self.style.map("Primary.TButton", background=[("active", "#1D4ED8"), ("disabled", "#9CA3AF")])
        
        # Estilo para Botones Secundarios / Peligro (Rojo/Gris)
        self.style.configure("Danger.TButton", background="#EF4444", foreground="white", font=("Arial", 9, "bold"), borderwidth=0)
        self.style.map("Danger.TButton", background=[("active", "#OFFF0000"), ("disabled", "#9CA3AF")])
        
        # Estilo para Botones de Acción AI (Verde Esmeralda)
        self.style.configure("Success.TButton", background="#10B981", foreground="white", font=("Arial", 9, "bold"), borderwidth=0)
        self.style.map("Success.TButton", background=[("active", "#059669"), ("disabled", "#9CA3AF")])
        
        self.setup_ui()
    
    def setup_ui(self):
        # Frame de búsqueda
        search_frame = ttk.LabelFrame(self.root, text=" Configuración de Búsqueda ", padding=12)
        search_frame.pack(fill="x", padx=15, pady=8)
        
        ttk.Label(search_frame, text="Tema de Búsqueda:").grid(row=0, column=0, sticky="w", pady=5)
        self.query_entry = ttk.Entry(search_frame, width=52, font=("Arial", 10))
        self.query_entry.grid(row=0, column=1, padx=8, sticky="w", pady=5)
        #self.query_entry.insert(0, "Educacion en Estados Unidos")
        
        ttk.Label(search_frame, text="Máximo de Posts:").grid(row=1, column=0, sticky="w", pady=5)
        self.max_posts_entry = ttk.Entry(search_frame, width=12, font=("Arial", 10))
        self.max_posts_entry.grid(row=1, column=1, padx=8, sticky="w", pady=5)
        self.max_posts_entry.insert(0, "10")
        ttk.Label(search_frame, text="(por red social)").grid(row=1, column=2, sticky="w", padx=2)
        
        # Botones de control de Scraping
        btn_frame = ttk.Frame(self.root, padding=5)
        btn_frame.pack(fill="x", padx=15, pady=5)
        
        self.start_btn = ttk.Button(btn_frame, text="▶ Iniciar Búsqueda", style="Primary.TButton", command=self.start_scraping)
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹ Parar Búsqueda", style="Danger.TButton", command=self.stop_scraping, state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        
        # Log de Actividad (Estilo Terminal Dark)
        log_frame = ttk.LabelFrame(self.root, text=" Log de Actividad ", padding=10)
        log_frame.pack(fill="both", expand=True, padx=15, pady=8)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            height=12, 
            bg="#111827",      # Fondo gris oscuro/negro cyberpunk
            fg="#10B981",      # Texto verde esmeralda brillante tipico de logs
            insertbackground="white", 
            font=("Consolas", 9)
        )
        self.log_text.pack(fill="both", expand=True)
        
        # Barra de Estado (Status)
        status_frame = ttk.Frame(self.root, padding=2)
        status_frame.pack(fill="x", padx=15, pady=5)
        self.status_label = ttk.Label(status_frame, text=" Estado: Inactivo", style="Status.TLabel", relief="sunken", padding=6)
        self.status_label.pack(fill="x")
        
        # Botones de Inteligencia Artificial
        self.button_Analize_Fellings()
    
    def log(self, message):
        """Agregar mensaje al log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.root.update()
    
    def start_scraping(self):
        """Iniciar el proceso de scraping"""
        query = self.query_entry.get().strip()
        if not query:
            messagebox.showerror("Error", "Debes ingresar un tema de búsqueda")
            return
        
        try:
            max_posts = int(self.max_posts_entry.get().strip())
            if max_posts <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "El máximo de posts debe ser un número entero positivo")
            return
        
        self.stop_event.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text=" Estado: Scraping activo...")
        
        networks = ["Instagram", "Facebook", "Twitter"]
        
        self.writer_process = Process(target=csv_writer_process, 
                                      args=(self.result_queue, self.stop_event))
        self.writer_process.start()
        self.log("Proceso de escritura CSV iniciado")
        
        for i, network in enumerate(networks):
            p = Process(target=ScraperGUI.run_scraper, 
                       args=(network, query, max_posts, self.result_queue, self.stop_event, i))
            p.start()
            self.processes.append(p)
            self.log(f"Iniciado scraper para {network} (PID: {p.pid})")
        
        self.log(f"Búsqueda iniciada: '{query}' (máx {max_posts} posts por red)")
        self.monitor_queue()
    
    def start_llm_analysis(self):
        """Inicia el análisis de LLMs en paralelo utilizando Gemini unificado"""        
        LLMs = ["Instagram", "Twitter", "Facebook"] 
        
        if not os.path.exists("resultados.csv"):
            messagebox.showerror("Error", "No existe resultados.csv para analizar")
            return

        self.log("Iniciando análisis asíncrono de sentimientos en paralelo (Google Gemini)...")
        
        self.llm_queue = Queue()
        self.active_llm_processes = 0

        for network in LLMs:
            p = Process(target=run_llm_process, args=(network, self.llm_queue))
            p.start()
            self.processes.append(p)
            self.active_llm_processes += 1
            self.log(f"🚀 Iniciado proceso paralelo LLM para: {network}")
        
        self.root.after(500, self.monitor_llm_queue)
    
    def mostrar_reporte(self, titulo: str, contenido: str):
        """Muestra el reporte en una ventana con scroll y tamaño reducido"""
        ventana_reporte = tk.Toplevel(self.root)
        ventana_reporte.title(titulo)
        ventana_reporte.geometry("600x400")
        ventana_reporte.configure(bg="#F3F4F6")
        
        frame_principal = ttk.Frame(ventana_reporte, padding=10)
        frame_principal.pack(fill="both", expand=True)
        
        ttk.Label(frame_principal, text=titulo, font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        texto_reporte = scrolledtext.ScrolledText(
            frame_principal,
            wrap=tk.WORD,
            width=70,
            height=20,
            bg="#1F2937",
            fg="#F9FAFB",
            font=("Consolas", 9)
        )
        texto_reporte.pack(fill="both", expand=True)
        texto_reporte.insert("1.0", contenido)
        texto_reporte.config(state="disabled")
        
        ttk.Button(
            frame_principal,
            text="Cerrar",
            style="Primary.TButton",
            command=ventana_reporte.destroy
        ).pack(pady=(10, 0))
        
        ventana_reporte.update_idletasks()
        x = (ventana_reporte.winfo_screenwidth() // 2) - (ventana_reporte.winfo_width() // 2)
        y = (ventana_reporte.winfo_screenheight() // 2) - (ventana_reporte.winfo_height() // 2)
        ventana_reporte.geometry(f"+{x}+{y}")
    
    def monitor_llm_queue(self):
        """Revisa si llegaron reportes de los LLMs"""
        try:
            while not self.llm_queue.empty():
                network, reporte = self.llm_queue.get_nowait()
                self.active_llm_processes -= 1
                
                self.log(f"✅ Análisis finalizado: {network}")
                
                if reporte:
                    titulo = f"Reporte LLM - {network}"
                    self.mostrar_reporte(titulo, reporte)
            
            if self.active_llm_processes > 0:
                self.root.after(500, self.monitor_llm_queue)
            else:
                self.log("Todos los análisis concurrentes LLM han terminado.")

        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error en monitor LLM: {e}")
            
    @staticmethod
    def run_scraper(network, query, max_posts, result_queue, stop_event, process_id):
        """Ejecutar scraper en proceso separado"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            try:
                if network == "Twitter":
                    from process.Process_Twitter import TwitterScraper
                    scraper = TwitterScraper(query, result_queue, stop_event, max_posts)
                    scraper.run(page)

                elif network == "Reddit":
                    from process.Process_Reddit import RedditScraper
                    scraper = RedditScraper(query, result_queue, stop_event, max_posts)
                    scraper.run(page)
                    
                elif network == "Instagram":
                    from process.Process_Instagram import InstagramScraper
                    scraper = InstagramScraper(query, result_queue, stop_event, max_posts)
                    scraper.run(page)
                    
                elif network == "Facebook":
                    from process.Process_Facebook import FacebookScraper
                    scraper = FacebookScraper(query, result_queue, stop_event, max_posts)
                    scraper.run(page)
                    
            except Exception as e:
                print(f"Error crítico en proceso {network}: {e}")
            finally:
                browser.close()
    
    def monitor_queue(self):
        """Monitorear la cola de resultados"""
        if not self.stop_event.is_set():
            try:
                while not self.result_queue.empty():
                    data = self.result_queue.get_nowait()
                    self.log(f"✓ {data['RedSocial']}: {data['idPublicacion']}")
            except queue.Empty:
                pass
            
            self.root.after(1000, self.monitor_queue)
    
    def stop_scraping(self):
        """Detener el scraping"""
        self.log("Deteniendo búsqueda...")
        self.stop_event.set()
        
        for p in self.processes:
            p.join(timeout=5)
            if p.is_alive():
                p.terminate()
        
        if self.writer_process:
            self.writer_process.join(timeout=5)
        
        self.processes.clear()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text=" Estado: Detenido")
        self.log("Búsqueda detenida. Datos guardados en resultados.csv")

    def button_Analize_Fellings(self):
        """Crea el botón en la interfaz."""        
        ai_frame = ttk.LabelFrame(self.root, text=" Dashboard & Inteligencia Artificial ", padding=12)
        ai_frame.pack(fill="x", padx=15, pady=10)
        
        btn_analisis = ttk.Button(ai_frame, text="🧠 Analizar Sentimientos (AI)", style="Success.TButton", command=self.start_llm_analysis)
        btn_analisis.pack(side="left", padx=6, pady=5)

        btn_graficas = ttk.Button(ai_frame, text="📊 Ver Gráficas", style="Primary.TButton", command=self.view_graphs)
        btn_graficas.pack(side="left", padx=6, pady=5)

        btn_detalles = ttk.Button(ai_frame, text="🔍 Ver Detalles", style="Primary.TButton", command=self.view_details)
        btn_detalles.pack(side="left", padx=6, pady=5)

    def _parse_report_counts(self, filepath, nombre_red):
        if not os.path.exists(filepath):
            self.log(f"[Gráficas] No se encontró el reporte de {nombre_red}: {filepath}")
            return None

        counts = {"Positivo": 0, "Negativo": 0, "Neutral": 0, "Error": 0}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    m = re.match(r"^[•\-\*]?\s*(Positivo|Negativo|Neutral|Error|Errores)\s*:\s*(\d+)", line, re.IGNORECASE)
                    if not m:
                        continue

                    label = m.group(1).strip().lower()
                    value = int(m.group(2))

                    if label == "positivo":
                        counts["Positivo"] = value
                    elif label == "negativo":
                        counts["Negativo"] = value
                    elif label == "neutral":
                        counts["Neutral"] = value
                    elif label in ("error", "errores"):
                        counts["Error"] = value
        except Exception as e:
            self.log(f"[Gráficas] Error leyendo {filepath}: {e}")
            return None

        return counts

    def _parse_report_times(self, filepath, nombre_red):
        if not os.path.exists(filepath):
            self.log(f"[Gráficas] No se encontró el reporte de {nombre_red}: {filepath}")
            return None

        times = {"tiempo_total": 0.0, "tiempo_promedio": 0.0}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    m_total = re.search(r"Tiempo Total(?: de Procesamiento)?\s*:\s*([0-9]+(?:\.[0-9]+)?)", line, re.IGNORECASE)
                    if m_total:
                        try:
                            times["tiempo_total"] = float(m_total.group(1))
                        except ValueError:
                            pass

                    m_avg = re.search(r"Tiempo Promedio(?: por Publicación)?(?:/Post)?\s*:\s*([0-9]+(?:\.[0-9]+)?)", line, re.IGNORECASE)
                    if m_avg:
                        try:
                            times["tiempo_promedio"] = float(m_avg.group(1))
                        except ValueError:
                            pass
        except Exception as e:
            self.log(f"[Gráficas] Error leyendo tiempos de {filepath}: {e}")
            return None

        return times

    def view_graphs(self):
        """Abre una ventana con gráficas de barras comparando rendimientos consolidados."""
        # CORREGIDO: Adaptados los nombres de los archivos de salida a la estructura unificada sin _grok
        redes = [
            ("Instagram", "reporte_instagram_openai.txt"),
            ("Twitter", "reporte_twitter.txt"),
            ("Facebook", "reporte_facebook_openai.txt"),
        ]

        datos_sentimientos = []
        datos_tiempos = []
        
        for nombre, archivo in redes:
            stats = self._parse_report_counts(archivo, nombre)
            if stats:
                datos_sentimientos.append((nombre, stats))
            
            times = self._parse_report_times(archivo, nombre)
            if times:
                datos_tiempos.append((nombre, times))

        if not datos_sentimientos and not datos_tiempos:
            messagebox.showerror("Error", "No se encontraron reportes consolidados para generar gráficas.")
            return

        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        fig.suptitle("Análisis de Sentimientos y Rendimiento Multi-Proceso", fontsize=14, fontweight="bold")

        if datos_sentimientos:
            sentimientos = ["Positivo", "Negativo", "Neutral", "Error"]
            x = list(range(len(sentimientos)))
            width = 0.2

            for idx, (nombre, stats) in enumerate(datos_sentimientos):
                valores = [stats.get(s, 0) for s in sentimientos]
                posiciones = [i + idx * width for i in x]
                axes[0].bar(posiciones, valores, width=width, label=nombre)

            axes[0].set_xticks([i + width for i in x])
            axes[0].set_xticklabels(sentimientos)
            axes[0].set_ylabel("Elementos Clasificados")
            axes[0].set_title("Distribución de Sentimientos")
            axes[0].legend()
            axes[0].grid(axis="y", linestyle="--", alpha=0.3)

        if datos_tiempos:
            nombres = [nombre for nombre, _ in datos_tiempos]
            tiempos_promedio = [times["tiempo_promedio"] for _, times in datos_tiempos]
            
            bars = axes[1].bar(nombres, tiempos_promedio, color=['#FF6B6B', '#4ECDC4', '#45B7D1'])
            axes[1].set_ylabel("Tiempo (segundos)")
            axes[1].set_title("Tiempo Promedio por Publicación")
            axes[1].grid(axis="y", linestyle="--", alpha=0.3)
            
            for bar, valor in zip(bars, tiempos_promedio):
                height = bar.get_height()
                axes[1].text(bar.get_x() + bar.get_width()/2., height, f'{valor:.2f}s', ha='center', va='bottom', fontsize=9)

        if datos_tiempos:
            nombres = [nombre for nombre, _ in datos_tiempos]
            tiempos_totales = [times["tiempo_total"] for _, times in datos_tiempos]
            
            bars = axes[2].bar(nombres, tiempos_totales, color=['#FF6B6B', '#4ECDC4', '#45B7D1'])
            axes[2].set_ylabel("Tiempo Total (segundos)")
            axes[2].set_title("Tiempo Total de Procesamiento LLM")
            axes[2].grid(axis="y", linestyle="--", alpha=0.3)
            
            for bar, valor in zip(bars, tiempos_totales):
                height = bar.get_height()
                axes[2].text(bar.get_x() + bar.get_width()/2., height, f'{valor:.2f}s', ha='center', va='bottom', fontsize=9)

        plt.tight_layout()

        ventana = tk.Toplevel(self.root)
        ventana.title("Dashboard de Rendimiento Asíncrono")
        ventana.geometry("1200x500")

        canvas = FigureCanvasTkAgg(fig, master=ventana)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        ventana.canvas = canvas
        ventana.figure = fig

    def view_details(self):
        # CORREGIDO: Adaptados los nombres de los archivos JSON a la estructura unificada sin _grok
        archivos = [
            ("Instagram", "analisis_instagram_completo.json"),
            ("Twitter", "analisis_twitter_completo.json"),
            ("Facebook", "analisis_facebook_completo.json"),
        ]

        ventana = tk.Toplevel(self.root)
        ventana.title("Detalles Estructurados por Publicación (JSON Data)")
        ventana.geometry("900x500")

        notebook = ttk.Notebook(ventana)
        notebook.pack(fill="both", expand=True)

        tabs_creados = 0

        for nombre, archivo in archivos:
            if not os.path.exists(archivo):
                self.log(f"[Detalles] No se encontró archivo: {archivo}")
                continue

            try:
                with open(archivo, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                self.log(f"[Detalles] Error leyendo {archivo}: {e}")
                continue

            if not isinstance(data, list) or not data:
                continue

            frame = ttk.Frame(notebook)
            notebook.add(frame, text=nombre)
            tabs_creados += 1

            columnas = ("id", "sent_general", "sent_post", "total_com", "total_anal")
            tree = ttk.Treeview(frame, columns=columnas, show="headings", height=20)

            tree.heading("id", text="ID Publicación")
            tree.heading("sent_general", text="Sent. General")
            tree.heading("sent_post", text="Sent. Post")
            tree.heading("total_com", text="# Comentarios")
            tree.heading("total_anal", text="# Coment. Analizados")

            tree.column("id", width=260, anchor="w")
            tree.column("sent_general", width=100, anchor="center")
            tree.column("sent_post", width=100, anchor="center")
            tree.column("total_com", width=110, anchor="center")
            tree.column("total_anal", width=140, anchor="center")

            vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)

            tree.grid(row=0, column=0, sticky="nsew")
            vsb.grid(row=0, column=1, sticky="ns")

            frame.rowconfigure(0, weight=1)
            frame.columnconfigure(0, weight=1)

            max_rows = 300
            for idx, item in enumerate(data):
                if idx >= max_rows:
                    break

                id_pub = item.get("idPublicacion", "")
                sent_general = item.get("sentimiento_general", "")

                analisis_post = item.get("analisis_post") or {}
                sent_post = analisis_post.get("sentimiento", "")

                total_com = item.get("total_comentarios", 0)
                total_anal = item.get("total_analizados", 0)

                tree.insert("", "end", values=(id_pub, sent_general, sent_post, total_com, total_anal))

        if tabs_creados == 0:
            ventana.destroy()
            messagebox.showerror("Error", "No se encontraron archivos JSON de análisis para mostrar detalles.")


if __name__ == "__main__":
    mp.set_start_method('spawn', force=True)
    root = tk.Tk()
    app = ScraperGUI(root)
    root.mainloop()