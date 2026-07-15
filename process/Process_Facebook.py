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

    def waitForManualUserLogin(self, browserPage):
        print("[Facebook] --- ESPERANDO INICIO DE SESIÓN MANUAL ---")
        maxRetries = 300 
        for i in range(maxRetries):
            if self.stop_event.is_set():
                return False
            try:
                # Verificamos si estamos en el feed o con sesión iniciada
                if browserPage.query_selector('div[role="feed"]') or \
                   browserPage.query_selector('input[placeholder*="Facebook"]'):
                    print("[Facebook] ¡Sesión detectada!")
                    return True
            except Exception:
                pass
            time.sleep(1)
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

            # Flujo interactivo de búsqueda desde el buscador superior de la Home
            print(f"[Facebook] Buscando tema de forma humana desde la interfaz superior...")
            try:
                search_box_selector = 'input[placeholder*="Buscar"], input[placeholder*="Search"], input[type="search"]'
                browserPage.wait_for_selector(search_box_selector, timeout=15000)
                
                browserPage.click(search_box_selector)
                browserPage.locator(search_box_selector).fill("") 
                
                # Escritura humana carácter por carácter
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

            # Verificación de seguridad: esperar a que el DOM pinte el feed de resultados
            try:
                browserPage.wait_for_selector('div[role="feed"], div[role="article"], div[data-testid="post_message"]', timeout=15000)
                print("[Facebook] Interfaz de búsqueda detectada con éxito.")
            except Exception:
                print("[Facebook] Advertencia: Tiempo de espera de elementos agotado. Forzando ruta cronológica posts...")
                cleanQuery = self.query.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
                browserPage.goto(f"https://www.facebook.com/search/posts/?q={cleanQuery}")
                self.executeRandomSleep(6, 9)

            extractedCount = 0
            stallCounter = 0  
            maxStallIterations = 15  # Aumentado a 15 para dar más margen de carga en conexiones lentas
            maxIterations = 120  # Más intentos máximos para búsquedas grandes (ej: 20 posts)
            iteration = 0
            
            while not self.stop_event.is_set() and extractedCount < self.max_posts and iteration < maxIterations:
                iteration += 1
                previousCount = extractedCount
                
                # Múltiples scrolls intermedios pausados para asegurar que Facebook despierte el Lazy Loading
                for _ in range(4):
                    browserPage.evaluate("window.scrollBy(0, window.innerHeight * 1.5)")
                    time.sleep(0.6)
                
                self.executeRandomSleep(2, 4)

                # Selectores combinados para abarcar todos los formatos de publicación de Facebook
                potentialPosts = browserPage.query_selector_all('div[role="article"]')
                if len(potentialPosts) == 0:
                    potentialPosts = browserPage.query_selector_all('div[data-testid="post_message"]') or \
                                     browserPage.query_selector_all('div[data-ad-comet-preview="message"]')

                print(f"[Facebook] Iteración {iteration}: {len(potentialPosts)} candidatos en el DOM. Progreso: {extractedCount}/{self.max_posts}")

                for post in potentialPosts:
                    if self.stop_event.is_set() or extractedCount >= self.max_posts:
                        break
                    
                    try:
                        rawText = post.inner_text().strip()
                        if len(rawText) < 40: continue
                        if "Se incluyen los resultados" in rawText: continue

                        # ID unívoco para control estricto de duplicados en el feed
                        postId = str(hash(rawText[:150]))

                        if postId not in self.processed_posts:
                            dataPayload = {
                                'RedSocial': 'Facebook',
                                'IDP': self.process_id,
                                'Request': self.query,
                                'FechaPeticion': self.request_date,
                                'FechaPublicacion': datetime.now().strftime("%Y-%m-%d"),
                                'idPublicacion': f"FB_{postId[:8]}",
                                'Data': rawText.replace('\n', ' ').replace('|', '-')[:2200]
                            }
                            
                            self.result_queue.put(dataPayload)
                            self.processed_posts.add(postId)
                            extractedCount += 1
                            print(f"[Facebook] ✓ ¡ÉXITO! Post {extractedCount}/{self.max_posts} extraído: FB_{postId[:8]}")
                            self.executeRandomSleep(0.5, 1.2)
                        
                    except Exception:
                        continue
                
                # Manejo inteligente del estancamiento: Solo se rinde si realmente no hay más contenido en la plataforma
                if extractedCount == previousCount:
                    stallCounter += 1
                    if stallCounter >= maxStallIterations:
                        print(f"[Facebook] Deteniendo: El feed no cargó contenido nuevo tras {maxStallIterations} scrolls profundos.")
                        break
                else:
                    stallCounter = 0  
                    
            print(f"[Facebook] Finalizado: {extractedCount} posts extraídos de forma limpia.")
                        
        except Exception as error:
            print(f"[Facebook] Error crítico en ejecución: {error}")