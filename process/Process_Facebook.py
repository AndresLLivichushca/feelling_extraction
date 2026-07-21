import time
import random
from datetime import datetime
import json
import os

class FacebookScraper:
    def __init__(self, search_query, result_queue, stop_event, max_posts=50):
        self.query = search_query
        self.result_queue = result_queue
        self.stop_event = stop_event
        self.max_posts = max_posts
        self.process_id = os.getpid()
        self.request_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.processed_posts = set()

    def executeRandomSleep(self, minimumSeconds=2.0, maximumSeconds=4.0):
        """Simula comportamiento humano para evitar bloqueos del WAF"""
        time.sleep(random.uniform(minimumSeconds, maximumSeconds))

    def saveSessionCookies(self, browserPage):
        try:
            sessionCookies = browserPage.context.cookies()
            with open('facebook_cookies.json', 'w') as fileHandle:
                json.dump(sessionCookies, fileHandle)
            print("[Facebook] Cookies guardadas exitosamente.")
        except Exception as error:
            print(f"[Facebook] Error guardando cookies: {error}")

    def loadSessionCookies(self, browserPage):
        if os.path.exists('facebook_cookies.json'):
            try:
                with open('facebook_cookies.json', 'r') as fileHandle:
                    sessionCookies = json.load(fileHandle)
                    browserPage.context.add_cookies(sessionCookies)
                return True
            except Exception as error:
                print(f"[Facebook] Error cargando cookies: {error}")
        return False

    def run(self, browserPage):
        try:
            browserPage.set_default_timeout(60000)
            self.loadSessionCookies(browserPage)

            print("[Facebook] Inicializando y verificando estado de sesión...")
            browserPage.goto("https://www.facebook.com/")
            self.executeRandomSleep(3, 5)

            # CONTROL DE ACCESO CON PAUSA ABSOLUTA EN TERMINAL
            if browserPage.query_selector('input[name="email"]') or "login" in browserPage.url:
                print("\n" + "!"*70)
                print(" [⚠️ PAUSA DE SEGURIDAD] ACCESO REQUERIDO PARA FACEBOOK")
                print(" 1. Dirígete a la ventana automatizada de Chromium que se acaba de abrir.")
                print(" 2. Inicia sesión manualmente con tu cuenta de Facebook.")
                print(" 3. Asegúrate de estar completamente dentro del Home / Feed de Facebook.")
                print(" 4. CUANDO HAYAS TERMINADO, regresa aquí a la terminal y presiona ENTER.")
                print("!"*70 + "\n")
                
                input(">>> PRESIONA ENTER AQUÍ EN LA TERMINAL CUANDO YA ESTÉS LOGUEADO EN FACEBOOK...")
                print("[Facebook] Reanudando ejecución y guardando nueva sesión...")
                self.saveSessionCookies(browserPage)

            print(f"[Facebook] Buscando tema de forma humana desde la interfaz superior...")
            try:
                search_box_selector = 'input[placeholder*="Buscar"], input[placeholder*="Search"], input[type="search"]'
                browserPage.wait_for_selector(search_box_selector, timeout=15000)
                browserPage.click(search_box_selector)
                browserPage.locator(search_box_selector).fill("") 
                
                for char in self.query:
                    browserPage.keyboard.type(char)
                    time.sleep(random.uniform(0.05, 0.12))
                    
                browserPage.keyboard.press("Enter")
                print("[Facebook] Búsqueda enviada. Esperando renderizado de resultados...")
                self.executeRandomSleep(6, 9)
                
            except Exception as search_error:
                print(f"[Facebook] Falló búsqueda interactiva: {search_error}. Aplicando redirección forzada...")
                cleanQuery = self.query.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
                browserPage.goto(f"https://www.facebook.com/search/posts/?q={cleanQuery}")
                self.executeRandomSleep(6, 9)

            try:
                browserPage.wait_for_selector('div[role="feed"], div[role="article"], div[data-testid="post_message"]', timeout=15000)
                print("[Facebook] Interfaz de búsqueda detectada con éxito.")
            except Exception:
                cleanQuery = self.query.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
                browserPage.goto(f"https://www.facebook.com/search/posts/?q={cleanQuery}")
                self.executeRandomSleep(6, 9)

            extractedCount = 0
            stallCounter = 0  
            maxStallIterations = 15  
            maxIterations = 120  
            iteration = 0
            
            while not self.stop_event.is_set() and extractedCount < self.max_posts and iteration < maxIterations:
                iteration += 1
                previousCount = extractedCount
                
                for _ in range(4):
                    browserPage.evaluate("window.scrollBy(0, window.innerHeight * 1.5)")
                    time.sleep(0.6)
                self.executeRandomSleep(2, 4)

                potentialPosts = browserPage.query_selector_all('div[role="article"]')
                if len(potentialPosts) == 0:
                    potentialPosts = browserPage.query_selector_all('div[data-testid="post_message"]') or \
                                     browserPage.query_selector_all('div[data-ad-comet-preview="message"]')

                print(f"[Facebook] Iteración {iteration}: {len(potentialPosts)} candidatos en el DOM. Progreso: {extractedCount}/{self.max_posts}")

                for post in potentialPosts:
                    if self.stop_event.is_set() or extractedCount >= self.max_posts:
                        break
                    
                    try:
                        # Capturar la descripción limpia del Post
                        msg_elem = post.query_selector('div[data-testid="post_message"]') or \
                                   post.query_selector('div[data-ad-comet-preview="message"]') or \
                                   post.query_selector('div[dir="auto"]')
                        
                        post_text = msg_elem.inner_text().strip() if msg_elem else post.inner_text().strip()
                        if len(post_text) < 25 or "Se incluyen los resultados" in post_text: 
                            continue

                        postId = str(hash(post_text[:150]))
                        if postId in self.processed_posts: 
                            continue
                        
                        print(f"   ↳ [Facebook] Extrayendo debates del post FB_{postId[:8]}...")
                        
                        # INTENTO AGRESIVO DE DESPLIEGUE: Forzar clic en los botones de interacción por texto
                        botones_comentarios = post.query_selector_all('div[role="button"]:has-text("Comentarios"), div[role="button"]:has-text("Comments"), span:has-text("comentario")')
                        for btn in botones_comentarios:
                            try:
                                btn.click()
                                browserPage.wait_for_timeout(2000)
                            except: pass
                        
                        # Scroll local simulado sobre la tarjeta del post
                        post.scroll_into_view_if_needed()
                        browserPage.wait_for_timeout(1000)

                        # SELECTOR SEMÁNTICO INMUNE A CAMBIOS: Extrae texto dentro de los bloques estructurados de comentario
                        comment_elements = post.query_selector_all('div[dir="auto"] div[dir="auto"]'), post.query_selector_all('div[role="comment"] span')
                        # Combinamos los dos enfoques de búsqueda de nodos de texto
                        nodes = post.query_selector_all('div[role="comment"]') or post.query_selector_all('span[dir="auto"]')
                        
                        list_comments = []
                        for node in nodes:
                            try:
                                c_text = node.inner_text().strip()
                                # Filtrar metadatos y la UI del post
                                if c_text and 8 < len(c_text) < 500 and c_text not in post_text and "Me gusta" not in c_text and "Responder" not in c_text and "Compartir" not in c_text:
                                    list_comments.append(c_text.replace('|', '-').replace('\n', ' '))
                            except: continue

                        list_comments = list(dict.fromkeys(list_comments))[:10]
                        print(f"   ↳ [Facebook] Encontrados {len(list_comments)} comentarios reales.")

                        # Formatear usando el delimitador lógico Pipe ('|')
                        final_data_payload = post_text.replace('\n', ' ').replace('|', '-')
                        if list_comments:
                            final_data_payload += " | " + " | ".join(list_comments)

                        dataPayload = {
                            'RedSocial': 'Facebook',
                            'IDP': self.process_id,
                            'Request': self.query,
                            'FechaPeticion': self.request_date,
                            'FechaPublicacion': datetime.now().strftime("%Y-%m-%d"),
                            'idPublicacion': f"FB_{postId[:8]}",
                            'Data': final_data_payload[:4500]
                        }
                        
                        self.result_queue.put(dataPayload)
                        self.processed_posts.add(postId)
                        extractedCount += 1
                        print(f"[Facebook] ✓ ¡PROCESADO! Post + Comentarios {extractedCount}/{self.max_posts}: FB_{postId[:8]}")
                        self.executeRandomSleep(1.0, 2.0)
                        
                    except Exception:
                        continue
                
                if extractedCount == previousCount:
                    stallCounter += 1
                    if stallCounter >= maxStallIterations:
                        print(f"[Facebook] Deteniendo: El feed no cargó contenido nuevo tras {maxStallIterations} scrolls.")
                        break
                else:
                    stallCounter = 0  
                    
            print(f"[Facebook] Finalizado: {extractedCount} publicaciones guardadas en la cola.")
                        
        except Exception as error:
            print(f"[Facebook] Error crítico en ejecución: {error}")