import time
import random
import os
from datetime import datetime

class YouTubeScraper:
    def __init__(self, query, result_queue, stop_event, max_posts=10):
        self.query = query
        self.result_queue = result_queue
        self.stop_event = stop_event
        self.max_posts = max_posts
        self.processed_videos = set()

    def run(self, page):
        print(f"[YouTube] Iniciando extracción interactiva profunda para: '{self.query}'")
        
        try:
            # PASO 1: Búsqueda directa en YouTube sin inicios de sesión obligatorios
            search_url = f"https://www.youtube.com/results?search_query={self.query.replace(' ', '+')}"
            page.goto(search_url, timeout=60000)
            time.sleep(random.uniform(4.0, 6.0))
            
            target_urls = []
            intentos_scroll = 0
            
            # Recolectar primero las URLs de los videos candidatos
            while len(target_urls) < self.max_posts and intentos_scroll < 8 and not self.stop_event.is_set():
                video_elements = page.query_selector_all('ytd-video-renderer')
                
                for element in video_elements:
                    try:
                        title_elem = element.query_selector('a#video-title')
                        if not title_elem: continue
                        
                        url_video = title_elem.get_attribute("href")
                        if url_video and "watch" in url_video:
                            full_url = f"https://www.youtube.com{url_video}"
                            if full_url not in self.processed_videos:
                                target_urls.append(full_url)
                                self.processed_videos.add(full_url)
                    except:
                        continue
                        
                page.evaluate("window.scrollBy(0, window.innerHeight);")
                time.sleep(random.uniform(2.0, 3.5))
                intentos_scroll += 1

            target_urls = list(dict.fromkeys(target_urls))[:self.max_posts]
            print(f"[YouTube] Encontrados {len(target_urls)} videos para desglose de comentarios.")

            # PASO 2: Navegar de uno en uno por los videos objetivos para extraer su debate interno
            videos_recolectados = 0
            for url in target_urls:
                if self.stop_event.is_set() or videos_recolectados >= self.max_posts:
                    break
                    
                try:
                    print(f"   ↳ [YouTube] Abriendo video: {url.split('v=')[1][:10]}...")
                    page.goto(url, timeout=45000)
                    time.sleep(random.uniform(3.0, 5.0))
                    
                    # Pausar el video inmediatamente si arranca el autoplay para optimizar ancho de banda/CPU
                    try:
                        page.keyboard.press("k") # Atajo nativo de YouTube para pausar
                    except: pass
                    
                    # Capturar el título del video
                    title_elem = page.query_selector('ytd-watch-metadata h1 yt-formatted-string') or page.query_selector('h1.title yt-formatted-string')
                    video_title = title_elem.inner_text().strip() if title_elem else "Video de YouTube"
                    
                    # Forzar scroll hacia abajo para activar la carga asíncrona de la caja de comentarios
                    page.evaluate("window.scrollTo(0, 600);")
                    time.sleep(3.0)
                    
                    # Hacer scrolls intermedios pausados para despertar hilos de debate ocultos
                    for _ in range(3):
                        page.evaluate("window.scrollBy(0, 500);")
                        time.sleep(1.5)
                        
                    # Extraer el contenido de los comentarios principales de la comunidad
                    comment_elements = page.query_selector_all('ytd-comment-thread-renderer #content-text')
                    list_comments = []
                    
                    for c_elem in comment_elements:
                        c_text = c_elem.inner_text().strip()
                        if c_text and 10 < len(c_text) < 400 and c_text not in video_title:
                            list_comments.append(c_text.replace('\n', ' ').replace('|', '-'))
                            
                    # Quitar duplicados y limitar a las 10 mejores opiniones por video
                    list_comments = list(dict.fromkeys(list_comments))[:10]
                    print(f"       ✓ Extraídos {len(list_comments)} comentarios reales del video.")
                    
                    # Empaquetar usando el delimitador lógico Pipe ('|') para consistencia del pipeline paralelo
                    final_payload = video_title
                    if list_comments:
                        final_payload += " | " + " | ".join(list_comments)
                        
                    id_publicacion = f"YT_{abs(hash(url)) % 10000000}"
                    
                    result_data = {
                        'RedSocial': 'YouTube',
                        'IDP': os.getpid(),
                        'Request': self.query,
                        'FechaPeticion': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'FechaPublicacion': datetime.now().strftime('%Y-%m-%d'),
                        'idPublicacion': id_publicacion,
                        'Data': final_payload[:4500]
                    }
                    
                    self.result_queue.put(result_data)
                    videos_recolectados += 1
                    print(f"   ✓ [YouTube] Guardado en cola Video #{videos_recolectados}: {id_publicacion}")
                    
                except Exception as video_error:
                    continue
                    
        except Exception as e:
            print(f"[YouTube][ERROR] Error crítico en navegación general: {e}")
            
        print(f"[YouTube] Extracción finalizada de manera exitosa. Total cosechados: {videos_recolectados}")