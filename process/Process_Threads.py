import time
import random
from datetime import datetime
import json
import os

class ThreadsScraper:
    def __init__(self, search_query, result_queue, stop_event, max_posts=10):
        self.query = search_query
        self.result_queue = result_queue
        self.stop_event = stop_event
        self.max_posts = max_posts
        self.process_id = os.getpid()
        self.request_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.processed_posts = set()

    def run(self, page):
        print(f"[Threads] Inicializando motor interactivo paralelo para: '{self.query}'")
        try:
            # Cargar estado completo (Cookies + LocalStorage) de Instagram o Threads
            archivo_sesion = 'threads_state.json' if os.path.exists('threads_state.json') else 'instagram_state.json'
            if os.path.exists(archivo_sesion) and os.path.getsize(archivo_sesion) > 0:
                try:
                    with open(archivo_sesion, 'r', encoding='utf-8') as f:
                        state = json.load(f)
                        if "cookies" in state: page.context.add_cookies(state["cookies"])
                    print(f"[Threads] Sesión cargada con éxito desde {archivo_sesion}")
                except Exception as e:
                    print(f"[Threads] Advertencia al inyectar sesión: {e}")

            # Navegar a la búsqueda de Threads
            search_url = f"https://www.threads.net/search?q={self.query.replace(' ', '%20')}"
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)

            target_links = []
            intentos_scroll = 0

            # Recolectar URLs directas a los hilos de debate
            while len(target_links) < self.max_posts and intentos_scroll < 12 and not self.stop_event.is_set():
                # Selector amplio para enlaces de publicaciones
                links = page.query_selector_all('a[href*="/post/"]') or page.query_selector_all('a[href*="/@"]')
                for link in links:
                    href = link.get_attribute("href")
                    if href and "/post/" in href:
                        if href.startswith('/'): href = f"https://www.threads.net{href}"
                        # Normalizar URL limpiando parámetros de búsqueda
                        clean_url = href.split('?')[0]
                        if clean_url not in self.processed_posts:
                            target_links.append(clean_url)
                            self.processed_posts.add(clean_url)
                
                page.evaluate("window.scrollBy(0, window.innerHeight * 0.8);")
                time.sleep(random.uniform(2.0, 3.5))
                intentos_scroll += 1

            target_links = list(dict.fromkeys(target_links))[:self.max_posts]
            print(f"[Threads] Cosechados {len(target_links)} enlaces de debates listos para desglose interno.")

            posts_recolectados = 0

            # Procesar cada hilo para extraer post principal + comentarios
            for url in target_links:
                if self.stop_event.is_set() or posts_recolectados >= self.max_posts:
                    break
                try:
                    post_shortcode = url.split('/post/')[1].replace('/', '')[:10]
                    print(f"   ↳ [Threads] Abriendo hilo de discusión: {post_shortcode}...")
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3000)

                    # Buscar todos los bloques de texto con atributo dir="auto"
                    text_nodes = page.query_selector_all('div[dir="auto"], span[dir="auto"]')
                    if not text_nodes: continue

                    textos_validos = []
                    for node in text_nodes:
                        t = node.inner_text().strip()
                        # Filtrar cadenas repetidas o de la interfaz de usuario
                        if t and 10 < len(t) < 500 and "Me gusta" not in t and "Respuestas" not in t and "Traducir" not in t:
                            textos_validos.append(t.replace('\n', ' ').replace('|', '-'))

                    textos_validos = list(dict.fromkeys(textos_validos))
                    if not textos_validos: continue

                    post_text = textos_validos[0]
                    list_comments = textos_validos[1:11]

                    print(f"       ✓ Extraídos {len(list_comments)} comentarios reales de Threads.")

                    final_payload = post_text
                    if list_comments:
                        final_payload += " | " + " | ".join(list_comments)

                    post_id = f"TH_{abs(hash(url)) % 10000000}"
                    result_data = {
                        'RedSocial': 'Threads',
                        'IDP': self.process_id,
                        'Request': self.query,
                        'FechaPeticion': self.request_date,
                        'FechaPublicacion': datetime.now().strftime("%Y-%m-%d"),
                        'idPublicacion': post_id,
                        'Data': final_payload[:4500]
                    }

                    self.result_queue.put(result_data)
                    posts_recolectados += 1
                    print(f"   ✓ [Threads] Guardado en cola Post #{posts_recolectados}: {post_id}")
                    time.sleep(random.uniform(1.5, 2.5))

                except Exception as e:
                    continue

        except Exception as e:
            print(f"[Threads][ERROR] Error en ejecución del módulo: {e}")
            
        print(f"[Threads] Extracción finalizada con éxito. Total cosechados: {posts_recolectados}")