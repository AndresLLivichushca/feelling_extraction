import os
import json
from playwright.sync_api import sync_playwright

def gestionar_login(plataforma, url_login):
    archivo_cookies = f"{plataforma.lower()}_cookies.json"
    print(f"\n==================================================")
    print(f"🔐 CONFIGURANDO SESIÓN PARA: {plataforma.upper()}")
    print(f"==================================================")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        # Si ya existen cookies previas, las cargamos para no perderlas
        context = browser.new_context()
        if os.path.exists(archivo_cookies):
            with open(archivo_cookies, 'r') as f:
                cookies = json.load(f)
                context.add_cookies(cookies)
                
        page = context.new_page()
        page.goto(url_login)
        
        print(f"\n[INSTRUCCIÓN]: Inicia sesión manualmente en la ventana de {plataforma}.")
        print("Cuando ya estés dentro del feed de inicio, CIERRA la ventana del navegador.")
        print("Esperando a que cierres la ventana para capturar tus credenciales de forma segura...")
        
        # El script se queda esperando activamente a que cierres la ventana manualmente
        while True:
            try:
                if page.is_closed():
                    break
                page.wait_for_timeout(1000)
            except:
                break
                
        # Al cerrar, capturamos el contexto de autenticación y lo persistimos
        try:
            cookies = context.cookies()
            with open(archivo_cookies, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2)
            print(f"✅ ¡ÉXITO! Cookies de {plataforma} guardadas en: '{archivo_cookies}'")
        except Exception as e:
            print(f"❌ No se pudieron guardar las cookies de {plataforma}: {e}")
            
        browser.close()
        
if __name__ == "__main__":
    # DICCIONARIO ACTUALIZADO: Reemplazamos Facebook por Threads para las 4 plataformas oficiales
    plataformas = [
        ("Instagram", "https://www.instagram.com/accounts/login/"),
        ("Threads", "https://www.threads.net/login"),
        ("Reddit", "https://www.reddit.com/login/"),
        ("YouTube", "https://www.youtube.com/")  # Abre YouTube para loguearte con Google si lo deseas
    ]
    
    print("🚀 INICIANDO ASISTENTE DE AUTENTICACIÓN PRE-CARGADA (THREADS EDITION)")
    for nombre, url in plataformas:
        gestionar_login(nombre, url)
        
    print("\n==================================================")
    print("🎉 ¡TODO LISTO! Todas las credenciales están cargadas.")
    print("Ya puedes ejecutar 'streamlit run app_web.py' con total seguridad.")
    print("==================================================")