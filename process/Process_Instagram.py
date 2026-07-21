import time
import random
import os
import json
from urllib.parse import quote
import re
from datetime import datetime

class InstagramScraper:
    def __init__(self, query, result_queue, stop_event, max_posts=50):
        self.query = query
        self.result_queue = result_queue
        self.stop_event = stop_event
        self.max_posts = max_posts
        
        self.process_id = os.getpid()
        self.request_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.session_path = "instagram_state.json"

    def _load_session(self, context):
        if os.path.exists(self.session_path) and os.path.getsize(self.session_path) > 0:
            try:
                with open(self.session_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if "cookies" in state:
                    context.add_cookies(state["cookies"])
                print(f"[Instagram] Sesión recuperada de {self.session_path} ✅")
                return True
            except Exception as e:
                print(f"[Instagram] Advertencia cargando sesión: {e}")
                return False
        return False

    def _dismiss_popups(self, page):
        try:
            btns = page.query_selector_all('button')
            for btn in btns:
                txt = btn.inner_text().lower()
                if "ahora no" in txt or "not now" in txt or "guardar información" in txt:
                    btn.click()
                    page.wait_for_timeout(1000)
                    break
        except Exception: pass

    def run(self, page):
        print(f"[Instagram] Inicializando worker interactivo (PID: {self.process_id})")
        page.set_default_timeout(60000)
        self._load_session(page.context)
        
        try:
            page.goto("https://www.instagram.com", wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)
            self._dismiss_popups(page)
        except Exception as e:
            print(f"[Instagram] Error fatal de conexión: {e}")
            return

        clean_tag = self.query.replace("#", "").replace(" ", "").lower()
        clean_tag = clean_tag.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        target_url = f"https://www.instagram.com/explore/tags/{clean_tag}/"
        
        print(f"[Instagram] Saltando directo a exploración por Tag: {target_url}")
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(4)
            self._dismiss_popups(page)
        except Exception as e:
            print(f"[Instagram] Error cargando búsqueda: {e}")
            return

        extracted_count = 0
        iteration = 0
        processed_ids = set()

        while not self.stop_event.is_set() and extracted_count < self.max_posts and iteration < 30:
            iteration += 1
            self._dismiss_popups(page)
            
            page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
            time.sleep(random.uniform(2.5, 3.5))

            links = page.query_selector_all('a[href*="/p/"]')
            print(f"[Instagram] Iteración {iteration}: {len(links)} candidatos en pantalla.")

            for link in links:
                if extracted_count >= self.max_posts or self.stop_event.is_set():
                    break
                    
                try:
                    href = link.get_attribute('href')
                    if not href: continue
                    
                    post_shortcode = href.split('/p/')[1].replace('/', '').split('?')[0].strip()
                    if not post_shortcode or post_shortcode in processed_ids: continue
                    
                    print(f"   ↳ [Instagram] Abriendo modal para post: IG_{post_shortcode[:8]}...")
                    link.click()
                    page.wait_for_timeout(3500)

                    # Extraer caption del post principal
                    caption_elem = page.query_selector('h1') or page.query_selector('span[dir="auto"]')
                    post_text = caption_elem.inner_text().strip() if caption_elem else f"Publicación #{clean_tag}"
                    post_text = post_text.replace('\n', ' ').replace('|', '-').strip()

                    # CORREGIDO: Selector universal para extraer los comentarios reales
                    comment_nodes = page.query_selector_all('span[dir="auto"]')
                    list_comments = []
                    
                    for node in comment_nodes:
                        try:
                            c_text = node.inner_text().strip()
                            # Filtrar textos repetidos o de la interfaz de usuario
                            if c_text and 6 < len(c_text) < 400 and c_text not in post_text and "Responder" not in c_text and "Ver respuestas" not in c_text and "Me gusta" not in c_text:
                                list_comments.append(c_text.replace('\n', ' ').replace('|', '-'))
                        except: continue
                    
                    list_comments = list(dict.fromkeys(list_comments))[:10]
                    print(f"   ↳ [Instagram] Extraídos {len(list_comments)} comentarios reales.")

                    final_payload = post_text
                    if list_comments:
                        final_payload += " | " + " | ".join(list_comments)

                    data_row = {
                        "RedSocial": "Instagram",
                        "IDP": self.process_id,
                        "Request": self.query,
                        "FechaPeticion": self.request_date,
                        "FechaPublicacion": datetime.now().strftime("%Y-%m-%d"),
                        "idPublicacion": f"IG_{post_shortcode}",
                        "Data": final_payload[:4500]
                    }
                    
                    self.result_queue.put(data_row)
                    processed_ids.add(post_shortcode)
                    extracted_count += 1
                    print(f"[Instagram] ✓ ¡GUARDADO! {extracted_count}/{self.max_posts}: IG_{post_shortcode[:8]}")
                    
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1200)
                    
                except Exception:
                    try: page.keyboard.press("Escape")
                    except: pass
                    continue

        print(f"[Instagram] Proceso finalizado. Total cosechados: {extracted_count}")