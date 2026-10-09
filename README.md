# Mi Primer Agente de IA: Construcción de un Agente de Soporte con Python y Gemini 🤖

Este proyecto es un agente de soporte de Inteligencia Artificial que lee automáticamente las quejas o sugerencias de un cliente registradas en un Google Form, las analiza usando la API de **Gemini 3.8 Flash** (para clasificarlas y detectar el sentimiento), y registra el resultado en una base de datos de Google Sheets. Todo orquestado con Python.

## 🚀 Funcionalidades
- **Conexión a Google Sheets**: Lee datos de respuestas nuevas y actualiza celdas usando OAuth 2.0 de Google.
- **Análisis con IA (Google Gemini)**: Analiza el texto del cliente y devuelve información estructurada (JSON).
  - **Clasificación**: Categoriza en `Ventas`, `Soporte Técnico` o `Logística`.
  - **Análisis de Sentimiento**: Detecta si la opinión es `Positiva`, `Negativa` o `Neutra`.
- **Automatización**: Usa `schedule` para revisar la base de datos de forma automática cada determinado intervalo (por defecto, 15 minutos).

## 🛠️ Tecnologías Utilizadas
- **Lenguaje**: Python 3.9+
- **Librerías principales**:
  - `gspread` y `google-auth` para la manipulación de Google Sheets.
  - `google-genai` para la conexión con el modelo de Gemini.
  - `schedule` para la programación de tareas.
- **Servicios Externos**: 
  - Google Forms & Sheets (Entrada y Base de datos)
  - Google Cloud Console (OAuth 2.0)
  - Google AI Studio (API de Gemini)

## ⚙️ Configuración e Instalación

### 1. Clonar el repositorio e instalar dependencias
```bash
git clone https://github.com/TU_USUARIO/mi_agente_soporte.git
cd mi_agente_soporte
pip install gspread google-auth google-genai schedule
```

### 2. Configuración de Credenciales
Debido a medidas de seguridad, las credenciales no están incluidas en este repositorio.
1. **Google Sheets OAuth 2.0**: Debes descargar tu archivo `client_secrets.json` desde Google Cloud Console y colocarlo en la raíz del proyecto.
2. **API Key de Gemini**: Abre el archivo `agente_soporte.py` y reemplaza el texto `"PEGA_AQUI_TU_API_KEY"` por tu clave real obtenida de Google AI Studio.

### 3. Base de Datos
El script espera que exista un archivo en tu Google Drive llamado exactamente **"Respuestas de Quejas (Base de Datos)"** con las columnas A a F configuradas correctamente (A: Marca temporal, B: Nombre, C: Comentario, D: Clasificación IA, E: Sentimiento IA, F: Agente Ejecutado).

## 🏃 Ejecución
Para iniciar el agente de soporte, ejecuta en tu terminal:

```bash
python agente_soporte.py
```
*En el primer arranque, se te pedirá iniciar sesión en tu navegador web para otorgar acceso a tu cuenta de Google.*

## 🔒 Seguridad
Este repositorio cuenta con un archivo `.gitignore` configurado para prevenir la subida accidental del archivo `client_secrets.json` y `authorized_user.json` a internet, protegiendo así tus tokens de acceso personal y datos sensibles.

---
*Proyecto de práctica escolar.*
