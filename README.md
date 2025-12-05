🚨 Sistema de Transcripción de Emergencias
Sistema inteligente de transcripción y análisis de llamadas de emergencia para centros de despacho 123 en Colombia.
🌟 Características

🎙️ Transcripción Automática: Convierte audio de emergencias a texto usando AssemblyAI
🧠 Análisis Inteligente con IA: Detecta emociones, palabras críticas y severidad usando Llama 3.3
🗺️ Geolocalización: Extrae y mapea ubicaciones de emergencias en Colombia
🚦 Cola de Prioridad: Organiza llamadas por severidad automáticamente
📊 Analíticas: Dashboard con métricas e historial de llamadas
🇨🇴 Optimizado para Colombia: Detecta direcciones colombianas (Calle, Carrera, Avenida, etc.)

🔑 Configuración
Esta aplicación requiere dos API keys gratuitas:

AssemblyAI: Para transcripción de audio

Regístrate en: https://www.assemblyai.com/
Plan gratuito: 5 horas/mes


Groq: Para análisis con IA

Regístrate en: https://console.groq.com/
Plan gratuito con límite generoso



Configurar Secrets en Hugging Face

Ve a tu Space
Click en Settings → Repository secrets
Agrega estos secrets:

ASSEMBLYAI_API_KEY: Tu clave de AssemblyAI
GROQ_API_KEY: Tu clave de Groq



🚀 Uso

Cargar archivo de audio de emergencia (MP3, WAV, M4A, FLAC, OGG)
Click en "Procesar Llamada de Emergencia"
El sistema transcribe, analiza y clasifica la emergencia automáticamente

🛠️ Tecnologías

Streamlit
AssemblyAI (Transcripción)
Groq/Llama 3.3 (Análisis IA)
Folium (Mapas)
GeoPy (Geocodificación)

⚠️ Disclaimer
Esta es una aplicación de demostración. Para uso en producción en servicios de emergencia reales, se requieren certificaciones adicionales y cumplimiento de regulaciones.
