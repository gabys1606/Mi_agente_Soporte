import json
import os
import time
import schedule
import gspread
from google import genai
from google.genai import types

# ---------------------------------------------------------
# PASO 4.3 - SECCIÓN DE CONFIGURACIÓN
# ---------------------------------------------------------
ARCHIVO_CREDENCIALES = "client_secrets.json"
NOMBRE_HOJA = "Respuestas de Quejas (Base de Datos)"
GEMINI_API_KEY = "PEGA_AQUI_TU_API_KEY"
INTERVALO_MINUTOS = 1

# Índices de columnas (según la práctica, considerando que Google Sheets es índice 1)
# A (1) - Marca temporal
# B (2) - Tu Nombre
# C (3) - Describe tu queja...
# D (4) - Clasificación IA
# E (5) - Sentimiento IA
# F (6) - Agente Ejecutado
COLUMNA_CLASIFICACION = 4
COLUMNA_SENTIMIENTO = 5
COLUMNA_PROCESADO = 6

# Variable global para el cliente de Gemini
cliente_gemini = None

# ---------------------------------------------------------
# PASO 4.4 - FUNCIÓN: CONECTAR CON GOOGLE SHEETS
# ---------------------------------------------------------
def conectar_sheets():
    """
    Autentica al script con Google usando OAuth 2.0, busca la hoja de cálculo
    por su nombre y devuelve la primera pestaña (sheet1).
    """
    try:
        # Autenticación mediante OAuth 2.0 (usando el archivo client_secrets.json)
        # Esto abrirá el navegador la primera vez para autorizar.
        gc = gspread.oauth(
            credentials_filename=ARCHIVO_CREDENCIALES,
            # Se guarda el token para no pedir permisos cada vez
            authorized_user_filename='authorized_user.json' 
        )
        
        # Abre el documento por el nombre exacto
        documento = gc.open(NOMBRE_HOJA)
        
        # Obtiene la primera hoja de cálculo del documento
        hoja = documento.sheet1
        return hoja
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo de credenciales '{ARCHIVO_CREDENCIALES}'.")
        raise
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Error: No se encontró la hoja de cálculo con el nombre '{NOMBRE_HOJA}'.")
        print("Verifica mayúsculas, tildes y espacios.")
        raise
    except Exception as e:
        print(f"Error inesperado al conectar con Google Sheets: {e}")
        raise

# ---------------------------------------------------------
# PASO 4.5 - FUNCIÓN: ANALIZAR CON GEMINI
# ---------------------------------------------------------
def analizar_con_gemini(comentario):
    """
    Envía un comentario a Gemini 3.8 Flash y solicita que lo clasifique y detecte el sentimiento.
    Retorna un diccionario de Python con las claves 'clasificacion' y 'sentimiento'.
    """
    # 1. Definimos la instrucción del sistema (System Prompt)
    instruccion_sistema = (
        "Eres un analista experto de soporte al cliente. "
        "Tu única tarea es analizar quejas o sugerencias y responder estrictamente en formato JSON. "
        "No des explicaciones, no saludes, solo devuelve el JSON. "
        "El JSON debe tener exactamente dos claves: 'clasificacion' y 'sentimiento'.\n\n"
        "Reglas para los valores:\n"
        "- 'clasificacion' debe ser exactamente una de estas tres opciones: 'Ventas', 'Soporte Técnico' o 'Logística'.\n"
        "- 'sentimiento' debe ser exactamente una de estas tres opciones: 'Positivo', 'Negativo' o 'Neutro'."
    )
    
    # 2. Instrucción del usuario (User Prompt)
    instruccion_usuario = f"Analiza el siguiente comentario de un cliente:\n\"{comentario}\""
    
    # 3. Configuración para el modelo (indicando que queremos respuesta JSON)
    configuracion = types.GenerateContentConfig(
        system_instruction=instruccion_sistema,
        response_mime_type="application/json"
    )
    
    try:
        # 4. Llamada a la API de Gemini (usamos el modelo gemini-3.8-flash)
        respuesta = cliente_gemini.models.generate_content(
            model='gemini-3.8-flash',
            contents=instruccion_usuario,
            config=configuracion
        )
        
        texto_respuesta = respuesta.text
        
        if not texto_respuesta:
            raise ValueError("Gemini devolvió una respuesta vacía.")
            
        # 5. Limpiamos posibles bloques Markdown de código que a veces agrega la IA (ej. ```json ... ```)
        texto_limpio = texto_respuesta.strip()
        if texto_limpio.startswith("```json"):
            texto_limpio = texto_limpio[7:]
        if texto_limpio.startswith("```"):
            texto_limpio = texto_limpio[3:]
        if texto_limpio.endswith("```"):
            texto_limpio = texto_limpio[:-3]
        texto_limpio = texto_limpio.strip()
        
        # 6. Convertimos el texto JSON a un diccionario de Python
        resultado_json = json.loads(texto_limpio)
        
        # 7. Validamos que contenga las claves correctas y los valores permitidos
        if 'clasificacion' not in resultado_json or 'sentimiento' not in resultado_json:
            raise ValueError("El JSON no contiene las claves requeridas 'clasificacion' y 'sentimiento'.")
            
        clasificaciones_validas = ["Ventas", "Soporte Técnico", "Logística"]
        sentimientos_validos = ["Positivo", "Negativo", "Neutro"]
        
        if resultado_json['clasificacion'] not in clasificaciones_validas:
            raise ValueError(f"Clasificación inválida: {resultado_json['clasificacion']}")
            
        if resultado_json['sentimiento'] not in sentimientos_validos:
            raise ValueError(f"Sentimiento inválido: {resultado_json['sentimiento']}")
            
        return resultado_json
        
    except json.JSONDecodeError:
        raise ValueError(f"Gemini no devolvió un JSON válido. Respuesta cruda: {texto_respuesta}")
    except Exception as e:
        raise RuntimeError(f"Error al procesar con Gemini: {e}")

# ---------------------------------------------------------
# PASO 4.6 - FUNCIÓN: AGENTE PRINCIPAL
# ---------------------------------------------------------
def ejecutar_agente():
    """
    Función que orquesta todo el proceso: conecta a Sheets, lee filas,
    procesa las nuevas con Gemini y actualiza los resultados.
    """
    print("\n" + "="*50)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando ciclo de revisión del agente...")
    
    # 1. Conectar a Google Sheets
    try:
        hoja = conectar_sheets()
    except Exception as e:
        print("No se pudo conectar a Google Sheets en este ciclo. Se intentará en el siguiente.")
        return # Terminamos este ciclo pero el programa sigue vivo
        
    try:
        # 2. Obtener todas las filas (get_all_values retorna una lista de listas)
        todas_las_filas = hoja.get_all_values()
        
        if not todas_las_filas:
            print("La hoja de cálculo está completamente vacía.")
            return
            
        # 3. Omitimos la primera fila (los encabezados) y procesamos el resto
        # Enumerate nos ayuda a llevar cuenta de qué número de fila de Excel estamos editando.
        # En Python, el índice empieza en 0. Como saltamos la fila 1 (índice 0), 
        # el primer registro de cliente (índice 1) corresponde a la fila 2 de Sheets.
        
        hubo_nuevos_registros = False
        
        for indice_python, fila in enumerate(todas_las_filas[1:], start=2):
            # Aseguramos que la fila tenga suficientes columnas (por si está incompleta)
            # Fila en Sheets: [0:MarcaTemporal, 1:Nombre, 2:Comentario, 3:Clasif, 4:Sentim, 5:Procesado]
            while len(fila) < 6:
                fila.append("")
                
            nombre_cliente = fila[1].strip() if fila[1] else "Cliente Anónimo"
            comentario = fila[2].strip()
            procesado = fila[5].strip().upper()
            
            # 4. Filtramos las que ya están procesadas o están vacías
            if procesado == "SI":
                continue # Ya fue procesado, pasamos a la siguiente fila
                
            if not comentario:
                continue # Fila vacía o sin comentario, la ignoramos
                
            hubo_nuevos_registros = True
            print(f"\nProcesando fila {indice_python} - Cliente: {nombre_cliente}")
            
            try:
                # 5. Enviar el comentario a Gemini
                resultado_ia = analizar_con_gemini(comentario)
                clasificacion = resultado_ia['clasificacion']
                sentimiento = resultado_ia['sentimiento']
                
                print(f"  > Clasificación : {clasificacion}")
                print(f"  > Sentimiento   : {sentimiento}")
                
                # 6. Escribir resultados en Google Sheets
                hoja.update_cell(indice_python, COLUMNA_CLASIFICACION, clasificacion)
                hoja.update_cell(indice_python, COLUMNA_SENTIMIENTO, sentimiento)
                
                # Solo si el análisis y escritura fueron exitosos, marcamos "SI"
                hoja.update_cell(indice_python, COLUMNA_PROCESADO, "SI")
                print("  > Registro guardado exitosamente en la hoja.")
                
                # Pausa para no saturar las APIs (Sheets y Gemini)
                time.sleep(2)
                
            except Exception as e:
                # 7. Manejo de errores por fila individual
                print(f"  > Error al analizar o guardar la fila {indice_python}: {e}")
                print("  > Saltando esta fila por ahora. No ha sido marcada como procesada.")
                
        if not hubo_nuevos_registros:
            print("No se encontraron quejas nuevas para procesar.")
            
    except Exception as e:
        print(f"Ocurrió un error general leyendo/escribiendo en la hoja: {e}")
        
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Ciclo de revisión finalizado.")
    print("="*50)

# ---------------------------------------------------------
# PASO 4.7 - BLOQUE PRINCIPAL (PUNTO DE ENTRADA)
# ---------------------------------------------------------
if __name__ == "__main__":
    print("\nIniciando Sistema: Mi Primer Agente de Soporte con IA")
    
    # Validaciones iniciales
    if GEMINI_API_KEY == "PEGA_AQUI_TU_API_KEY" or GEMINI_API_KEY.strip() == "":
        print("\n[ERROR CRÍTICO] Falta configurar la API Key de Gemini.")
        print("Abre el archivo 'agente_soporte.py', busca 'PEGA_AQUI_TU_API_KEY' y cámbialo por tu clave real.")
        exit(1)
        
    if not os.path.exists(ARCHIVO_CREDENCIALES):
        print(f"\n[ERROR CRÍTICO] No se encontró el archivo '{ARCHIVO_CREDENCIALES}'.")
        print("Asegúrate de que descargaste tu archivo JSON de OAuth y lo pusiste en esta misma carpeta.")
        exit(1)
        
    try:
        # Inicializamos el cliente global de Gemini
        cliente_gemini = genai.Client(api_key=GEMINI_API_KEY)
        print("Cliente de Gemini inicializado correctamente.")
    except Exception as e:
        print(f"\n[ERROR CRÍTICO] No se pudo inicializar el cliente de Gemini: {e}")
        exit(1)
        
    print(f"\nEl agente se ejecutará por primera vez y luego cada {INTERVALO_MINUTOS} minutos.")
    print("Presiona Ctrl+C en cualquier momento para detener el programa de forma segura.")
    
    # 1. Ejecutar inmediatamente al arrancar
    ejecutar_agente()
    
    # 2. Programar ejecuciones automáticas
    schedule.every(INTERVALO_MINUTOS).minutes.do(ejecutar_agente)
    
    # 3. Mantener el script corriendo en un bucle
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n\n[AVISO] El programa ha sido detenido por el usuario (Ctrl+C). ¡Hasta luego!")
