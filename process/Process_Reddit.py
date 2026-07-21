import time
import random
import os
from datetime import datetime

class RedditScraper:
    def __init__(self, query, result_queue, stop_event, max_posts=10):
        self.query = query
        self.result_queue = result_queue
        self.stop_event = stop_event
        self.max_posts = max_posts
        self.processed_posts = set()

    def run(self, page):
        print(f"[Reddit] Iniciando extracción profunda y analítica para: '{self.query}'")
        
        try:
            # PASO 1: Inyectar scripts de ocultación avanzada (Anti-Fingerprinting)
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['es-419', 'es', 'en']});
            """)
            
            # PASO 2: Establecer sesión en la raíz limpia
            page.goto("https://www.reddit.com", timeout=60000)
            time.sleep(random.uniform(3.0, 5.0))
            
            # PASO 3: Ejecutar la búsqueda estructurada
            search_url = f"https://www.reddit.com/search/?q={self.query.replace(' ', '%20')}"
            page.goto(search_url, timeout=60000)
            time.sleep(random.uniform(4.0, 5.0))
            
            # Recolectar primero las URLs de los posts objetivos para no perder el contexto de la búsqueda
            target_urls = []
            intentos_scroll = 0
            
            while len(target_urls) < self.max_posts and intentos_scroll < 8:
                post_elements = page.query_selector_all('a[data-testid="post-title"]') or \
                                page.query_selector_all('a[id^="post-title-"]')
                
                for element in post_elements:
                    url_post = element.get_attribute("href")
                    if url_post and url_post not in self.processed_posts:
                        # Completar URL absoluta si viene relativa
                        if url_post.startswith('/'):
                            url_post = f"https://www.reddit.com{url_post}"
                        target_urls.append(url_post)
                        self.processed_posts.add(url_post)
                
                page.evaluate("window.scrollBy(0, window.innerHeight);")
                time.sleep(random.uniform(2.0, 3.5))
                intentos_scroll += 1

            target_urls = list(dict.fromkeys(target_urls))[:self.max_posts]
            print(f"[Reddit] Cosechados {len(target_urls)} enlaces de discusión listos para desglose interno.")

            # PASO 4: Navegar de forma interactiva e individual por cada hilo de discusión
            posts_recolectados = 0
            for url in target_urls:
                if self.stop_event.is_set() or posts_recolectados >= self.max_posts:
                    break
                    
                try:
                    print(f"   ↳ [Reddit] Abriendo hilo interactivo: {url.split('/comments/')[1][:15]}...")
                    page.goto(url, timeout=45000)
                    page.wait_for_timeout(3000)
                    
                    # Extraer el título y el cuerpo opcional del post principal
                    title_element = page.query_selector('h1')
                    title_text = title_element.inner_text().strip() if title_element else "Discusión en Comunidad"
                    
                    body_element = page.query_selector('div[data-click-id="text-body"]') or \
                                   page.query_selector('div[id$="-post-rtjson-content"]')
                    body_text = body_element.inner_text().strip() if body_element else ""
                    
                    full_post_content = f"{title_text} - {body_text}".strip()
                    full_post_content = full_post_content.replace('\n', ' ').replace('|', '-').strip()
                    
                    # Forzar scroll sutil dentro del hilo para activar la inyección reactiva de comentarios
                    page.evaluate("window.scrollBy(0, window.innerHeight * 0.5);")
                    page.wait_for_timeout(2000)
                    
                    # Capturar los bloques semánticos de comentarios reales (shreddit-comment o párrafos internos)
                    comment_nodes = page.query_selector_all('div[data-testid="comment"]') or \
                                    page.query_selector_all('shreddit-comment p') or \
                                    page.query_selector_all('-comment-rtjson-content p')
                    
                    list_comments = []
                    for node in comment_nodes:
                        c_text = node.inner_text().strip()
                        # Filtrar cadenas vacías, duplicadas o avisos de moderación automáticos de Reddit
                        if c_text and 10 < len(c_text) < 500 and c_text not in full_post_content and "AutoModerator" not in c_text:
                            list_comments.append(c_text.replace('\n', ' ').replace('|', '-'))
                    
                    list_comments = list(dict.fromkeys(list_comments))[:10] # Limitar a 10 comentarios por post
                    print(f"       ✓ Extraídos {len(list_comments)} comentarios reales del debate.")
                    
                    # Estructurar la trama unificada con el delimitador Pipe ('|')
                    final_payload = full_post_content
                    if list_comments:
                        final_payload += " | " + " | ".join(list_comments)
                        
                    id_publicacion = f"RD_{abs(hash(url)) % 10000000}"
                    
                    result_data = {
                        'RedSocial': 'Reddit',
                        'IDP': os.getpid(),
                        'Request': self.query,
                        'FechaPeticion': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'FechaPublicacion': datetime.now().strftime('%Y-%m-%d'),
                        'idPublicacion': id_publicacion,
                        'Data': final_payload[:4500]
                    }
                    
                    self.result_queue.put(result_data)
                    posts_recolectados += 1
                    print(f"   ✓ [Reddit] Inyectado con éxito Post #{posts_recolectados}: {id_publicacion}")
                    time.sleep(random.uniform(1.5, 3.0))
                    
                except Exception:
                    continue
                
        except Exception as e:
            print(f"[Reddit][ERROR] Ocurrió una interrupción en el navegador: {e}")
            
        print(f"[Reddit] Proceso finalizado. Total posts cosechados: {posts_recolectados}")