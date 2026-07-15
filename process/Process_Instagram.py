import time
import random
import os
import json
from urllib.parse import quote
import re
from datetime import datetime

class InstagramScraper:
    """
    Scraper de Instagram - Módulo de Procesamiento
    ----------------------------------------------------------------
    Este módulo gestiona la navegación automatizada en Instagram para la extracción de datos.
    Sigue una estrategia de extracción por cuadrícula optimizada para el feed de tags.
    
    Compatible con la arquitectura de 'main.py' y multiprocesamiento.
    """

    def __init__(self, query, result_queue, stop_event, max_posts=50):
        """
        Inicializa el scraper con los parámetros del orquestador.
        """
        self.query = query
        self.result_queue = result_queue
        self.stop_event = stop_event
        self.max_posts = max_posts
        
        # Identificadores para trazabilidad en el CSV de salida
        self.process_id = os.getpid()
        self.request_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Ruta predeterminada para persistencia de sesión
        self.session_path = "instagram_state.json"

    # ----------------------------------------------------------------
    # 1. GESTIÓN DE SESIÓN
    # ----------------------------------------------------------------

    def _load_session(self, context):
        """
        Intenta cargar el estado de autenticación (cookies y localStorage) desde un archivo JSON.
        """
        if os.path.exists(self.session_path):
            try:
                with open(self.session_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                
                if "cookies" in state:
                    context.add_cookies(state["cookies"])
                
                if "origins" in state:
                    origins = state["origins"]
                    ig_ls = {}
                    for o in origins:
                        if "instagram.com" in o["origin"]:
                            for item in o.get("localStorage", []):
                                ig_ls[item["name"]] = item["value"]
                    
                    if ig_ls:
                        script = f"""
                        (() => {{
                            const data = {json.dumps(ig_ls)};
                            for (const [k, v] of Object.entries(data)) {{
                                localStorage.setItem(k, v);
                            }}
                        }})();
                        """
                        context.add_init_script(script)
                        
                print(f"[Instagram] Sesión recuperada de {self.session_path} ✅")
                return True
            except Exception as e:
                print(f"[Instagram] Advertencia: Error cargando archivo de sesión: {e}")
                return False
        return False

    def _save_session(self, page):
        """
        Guarda el estado actual (Cookies + LocalStorage) en disco.
        """
        try:
            state = page.context.storage_state()
            with open(self.session_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            print(f"[Instagram] Sesión guardada exitosamente en {self.session_path} 💾")
        except Exception as e:
            print(f"[Instagram] Error al guardar sesión: {e}")

    # ----------------------------------------------------------------
    # 2. UTILIDADES DE NAVEGACIÓN Y DETECCIÓN
    # ----------------------------------------------------------------

    def _is_logged_in(self, page):
        """
        Verifica si hay una sesión activa analizando el DOM en busca de elementos exclusivos.
        """
        try:
            selectors = [
                'svg[aria-label="Home"]',
                'svg[aria-label="Inicio"]',
                'a[href="/direct/inbox/"]',
                'a[href="/explore/"]',
                'div[role="navigation"]'
            ]
            for s in selectors:
                if page.locator(s).count() > 0:
                    return True
            return False
        except Exception:
            return False

    def _wait_for_manual_login(self, page):
        """
        Bloquea la ejecución hasta que el usuario inicie sesión manualmente.
        """
        print("\n" + "="*60)
        print(" [ATENCIÓN] REQUIERE LOGIN MANUAL EN INSTAGRAM")
        print(" Por favor, introduce tus credenciales en la ventana del navegador.")
        print(" El sistema detectará automáticamente cuando entres.")
        print("="*60 + "\n")

        attempts = 0
        while not self.stop_event.is_set():
            if self._is_logged_in(page):
                print("[Instagram] Login manual detectado exitosamente 🔓")
                self._save_session(page)
                return True
            
            time.sleep(2)
            attempts += 1
            if attempts % 5 == 0:
                print(f"[Instagram] Esperando login... ({attempts*2} segundos transcurridos)")
                
            if attempts > 150: 
                print("[Instagram] Tiempo de espera de login agotado.")
                return False
        return False

    # ----------------------------------------------------------------
    # 3. MÉTODO PRINCIPAL (ENTRY POINT)
    # ----------------------------------------------------------------

    def run(self, page):
        """
        Función principal invocada por el proceso hijo.
        """
        print(f"[Instagram] Inicializando worker (PID: {self.process_id})")
        page.set_default_timeout(60000)
        
        # 1. Intentar cargar sesión previa
        self._load_session(page.context)
        
        print("[Instagram] Navegando a la página principal...")
        try:
            page.goto("https://www.instagram.com", wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)
        except Exception as e:
            print(f"[Instagram] Error fatal de conexión: {e}")
            return

        # 2. Verificar estado de autenticación
        session_valid = False
        if self._is_logged_in(page):
            print("[Instagram] Sesión válida verificada. ✅")
            session_valid = True
        else:
            print("[Instagram] No se detectó sesión activa.")
            if self._wait_for_manual_login(page):
                 session_valid = True
            else:
                print("[Instagram] No se pudo establecer sesión. Finalizando worker.")
                return

        if session_valid:
            # Forzar la estrategia de extracción directa por cuadrícula / grid
            clean_tag = self.query.replace("#", "").replace(" ", "").lower()
            clean_tag = clean_tag.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            target_url = f"https://www.instagram.com/explore/tags/{clean_tag}/"
            
            print(f"[Instagram] Saltando directo a exploración por Tag en Cuadrícula: {target_url}")
            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(5)
            except Exception as e:
                print(f"[Instagram] Error cargando búsqueda: {e}")
                return

            # Bucle de extracción sobre la Grid
            extracted_count = 0
            stall_counter = 0
            iteration = 0
            processed_ids = set()

            while not self.stop_event.is_set() and extracted_count < self.max_posts and iteration < 50:
                iteration += 1
                previous_count = extracted_count
                
                # Desplazamiento progresivo del scroll para gatillar carga perezosa de imágenes
                page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
                time.sleep(random.uniform(2.0, 3.5))

                # Extraer todas las publicaciones cargadas en el DOM (etiquetas <a> dirigidas a publicaciones)
                links = page.query_selector_all('a[href*="/p/"]')
                print(f"[Instagram] Iteración {iteration}: Detectados {len(links)} candidatos en la cuadrícula.")

                for link in links:
                    if extracted_count >= self.max_posts or self.stop_event.is_set():
                        break
                        
                    try:
                        href = link.get_attribute('href')
                        if not href: continue
                        
                        # Generar el identificador único robusto
                        post_shortcode = href.split('/p/')[1].replace('/', '')
                        if post_shortcode in processed_ids:
                            continue

                        # El atributo 'alt' de la imagen dentro de la cuadrícula contiene la descripción (caption)
                        img_elem = link.query_selector('img')
                        raw_text = img_elem.get_attribute('alt') if img_elem else ""
                        
                        if not raw_text or len(raw_text.strip()) < 10:
                            raw_text = f"Publicación visual relacionada con la temática de búsqueda #{clean_tag}."

                        # Sanitizar el texto plano para preservar la coherencia del CSV delimitado por tuberías
                        clean_payload = raw_text.replace('\n', ' ').replace('|', '-').strip()

                        data_row = {
                            "RedSocial": "Instagram",
                            "IDP": self.process_id,
                            "Request": self.query,
                            "FechaPeticion": self.request_date,
                            "FechaPublicacion": datetime.now().strftime("%Y-%m-%d"),
                            "idPublicacion": f"IG_{post_shortcode}",
                            "Data": clean_payload[:4500]
                        }
                        
                        # Colocar payload estructurado en el búfer multiproceso
                        self.result_queue.put(data_row)
                        processed_ids.add(post_shortcode)
                        extracted_count += 1
                        print(f"[Instagram] ✓ ¡ÉXITO! Guardado Post {extracted_count}/{self.max_posts}: IG_{post_shortcode[:8]}")
                        time.sleep(random.uniform(0.3, 1.0))
                        
                    except Exception:
                        continue

                # Control dinámico de estancamiento de buffers del DOM
                if extracted_count == previous_count:
                    stall_counter += 1
                    if stall_counter >= 5:
                        print("[Instagram] No se detectó nueva data en la grid. Finalizando extracción.")
                        break
                else:
                    stall_counter = 0

            print(f"[Instagram] Proceso finalizado. Total de elementos inyectados: {extracted_count}")