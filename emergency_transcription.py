import streamlit as st
import requests
import json
from datetime import datetime
import re
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import pandas as pd

# Configure the page
st.set_page_config(
    page_title="Sistema de Transcripción de Emergencias",
    page_icon="🚨",
    layout="wide"
)

# API Keys - Se cargan desde Streamlit secrets en producción o del código en local
try:
    ASSEMBLYAI_API_KEY = st.secrets["ASSEMBLYAI_API_KEY"]
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    # Fallback para desarrollo local - Coloca tus claves aquí
    ASSEMBLYAI_API_KEY = "tu_clave_assemblyai_aqui"
    GROQ_API_KEY = "tu_clave_groq_aqui"

# Initialize session state
if 'call_history' not in st.session_state:
    st.session_state.call_history = []
if 'priority_queue' not in st.session_state:
    st.session_state.priority_queue = []
if 'assemblyai_key' not in st.session_state:
    st.session_state.assemblyai_key = ASSEMBLYAI_API_KEY
if 'groq_key' not in st.session_state:
    st.session_state.groq_key = GROQ_API_KEY

def analyze_transcript_with_llm(transcript):
    """Analyze transcript using LLM for emotions, keywords, and priority"""
    api_key = st.session_state.get('groq_key', '')
    
    if not api_key:
        return None
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    prompt = f"""Analiza esta transcripción de llamada de emergencia y extrae la siguiente información en formato JSON:

Transcripción: "{transcript}"

Responde SOLO con un objeto JSON válido (sin texto adicional, sin markdown, sin backticks) con esta estructura:
{{
    "emocion": "ESTRÉS ALTO" o "ESTRÉS MODERADO" o "CALMA",
    "icono_emocion": "🔴" o "🟡" o "🟢",
    "palabras_criticas": [
        {{"categoria": "nombre de categoría", "palabra": "palabra detectada", "severidad": "ALTA" o "MEDIA"}}
    ],
    "severidad_general": "Crítico" o "Alto" o "Medio" o "Bajo",
    "tipo_emergencia": "Médica" o "Incendio" o "Policía" o "Otro",
    "justificacion": "breve explicación de por qué se asignó esta severidad"
}}

Considera:
- ESTRÉS ALTO (🔴): pánico evidente, gritos, urgencia extrema
- ESTRÉS MODERADO (🟡): preocupación notable pero controlada
- CALMA (🟢): tono tranquilo y descriptivo

Palabras críticas a buscar (pero no limitarse a):
- Armas: pistola, arma, cuchillo, disparo
- Médico: sangre, inconsciente, infarto, no respira
- Fuego: incendio, humo, explosión
- Violencia: asalto, secuestro, golpes
- Vulnerable: niño, bebé, anciano, embarazada"""

    data = {
        'model': 'llama-3.3-70b-versatile',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.1,
        'max_tokens': 500
    }
    
    try:
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code != 200:
            return None
        
        content = response.json()['choices'][0]['message']['content'].strip()
        
        # Clean any markdown formatting
        content = content.replace('```json', '').replace('```', '').strip()
        
        analysis = json.loads(content)
        return analysis
    except Exception as e:
        st.warning(f"Error en análisis LLM: {str(e)}")
        return None

def extract_location(text):
    """Extract potential location information from text"""
    # Colombian address patterns
    patterns = [
        r'(?:calle|carrera|avenida|transversal|diagonal|circunvalar)\s+\d+[a-z]?\s*#?\s*\d+-?\d*',
        r'kr?\s*\.?\s*\d+[a-z]?\s*#?\s*\d+-?\d*',
        r'cl?\s*\.?\s*\d+[a-z]?\s*#?\s*\d+-?\d*',
        r'av?\s*\.?\s*\d+[a-z]?\s*#?\s*\d+-?\d*',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    
    # Also look for neighborhood/locality mentions
    locality_pattern = r'(?:barrio|localidad|sector)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ\s]+)'
    locality_match = re.search(locality_pattern, text, re.IGNORECASE)
    if locality_match:
        return locality_match.group(0)
    
    return None

def geocode_location(address):
    """Convert address to coordinates"""
    try:
        geolocator = Nominatim(user_agent="emergency_app_colombia", timeout=10)
        
        # Try multiple variations
        search_queries = [
            f"{address}, Bogotá, Colombia",
            f"{address}, Colombia",
            f"Bogotá, {address}, Colombia"
        ]
        
        for query in search_queries:
            try:
                location = geolocator.geocode(query)
                if location:
                    return location.latitude, location.longitude
            except:
                continue
        
        return None
    except Exception as e:
        st.warning(f"Error al geocodificar: {str(e)}")
        return None

def create_map(lat, lon, address):
    """Create map with emergency location"""
    m = folium.Map(location=[lat, lon], zoom_start=16)
    
    # Add emergency location marker
    folium.Marker(
        [lat, lon],
        popup=f"<b>Ubicación de Emergencia:</b><br>{address}",
        tooltip="Ubicación de Emergencia",
        icon=folium.Icon(color='red', icon='exclamation-triangle', prefix='fa')
    ).add_to(m)
    
    # Add radius circle
    folium.Circle(
        radius=500,
        location=[lat, lon],
        popup="Radio de 500m",
        color="crimson",
        fill=True,
        fillOpacity=0.1,
    ).add_to(m)
    
    return m

def transcribe_audio(audio_file):
    """Transcribe audio using AssemblyAI's free tier"""
    api_key = st.session_state.get('assemblyai_key', '')
    
    if not api_key:
        st.error("Por favor ingrese su clave API de AssemblyAI en la barra lateral")
        return None
    
    headers = {'authorization': api_key}
    
    # Upload audio file
    with st.spinner('Subiendo audio...'):
        upload_response = requests.post(
            'https://api.assemblyai.com/v2/upload',
            headers=headers,
            data=audio_file
        )
        
        if upload_response.status_code != 200:
            st.error(f"Error al subir: {upload_response.text}")
            return None
            
        audio_url = upload_response.json()['upload_url']
    
    # Request transcription with Spanish language
    with st.spinner('Transcribiendo audio...'):
        transcript_request = {
            'audio_url': audio_url,
            'language_code': 'es'  # Spanish
        }
        
        transcript_response = requests.post(
            'https://api.assemblyai.com/v2/transcript',
            json=transcript_request,
            headers=headers
        )
        
        if transcript_response.status_code != 200:
            st.error(f"Error en solicitud de transcripción: {transcript_response.text}")
            return None
            
        transcript_id = transcript_response.json()['id']
    
    # Poll for completion
    polling_endpoint = f'https://api.assemblyai.com/v2/transcript/{transcript_id}'
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    while True:
        polling_response = requests.get(polling_endpoint, headers=headers)
        transcript_result = polling_response.json()
        
        status = transcript_result['status']
        status_text.text(f"Estado: {status}")
        
        if status == 'completed':
            progress_bar.progress(100)
            status_text.empty()
            return transcript_result['text']
        elif status == 'error':
            st.error(f"Error en transcripción: {transcript_result.get('error', 'Error desconocido')}")
            return None
        
        progress_bar.progress(50)
        import time
        time.sleep(3)

def generate_summary(transcript):
    """Generate summary using Groq's free API"""
    api_key = st.session_state.get('groq_key', '')
    
    if not api_key:
        st.error("Por favor ingrese su clave API de Groq en la barra lateral")
        return None
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    prompt = f"""Eres un asistente de despacho de emergencias en Colombia. Analiza esta transcripción de llamada de emergencia y proporciona un resumen estructurado.

Transcripción: {transcript}

Proporciona un resumen en el siguiente formato:
- **Tipo de Emergencia**: [Médica/Incendio/Policía/Otro]
- **Nivel de Severidad**: [Crítico/Alto/Medio/Bajo]
- **Ubicación**: [Extrae cualquier información de ubicación mencionada]
- **Detalles Clave**: [Puntos principales de la llamada]
- **Acciones Inmediatas Requeridas**: [Qué deben saber/hacer los respondedores]

Sé conciso pero incluye toda la información crítica."""

    data = {
        'model': 'llama-3.3-70b-versatile',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.3,
        'max_tokens': 1000
    }
    
    with st.spinner('Generando resumen de emergencia...'):
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            st.error(f"Error al generar resumen: {response.text}")
            return None
        
        return response.json()['choices'][0]['message']['content']

def highlight_keywords(text, palabras_criticas):
    """Highlight critical keywords in text"""
    if not palabras_criticas:
        return text
    
    highlighted = text
    for item in palabras_criticas:
        palabra = item.get('palabra', '')
        severidad = item.get('severidad', 'MEDIA')
        color = 'red' if severidad == 'ALTA' else 'orange'
        
        highlighted = re.sub(
            f'({re.escape(palabra)})',
            f'<span style="background-color:{color};color:white;padding:2px 4px;border-radius:3px;font-weight:bold;">\\1</span>',
            highlighted,
            flags=re.IGNORECASE
        )
    return highlighted

# Sidebar
with st.sidebar:
    st.header("📊 Estado del Sistema")
    
    if ASSEMBLYAI_API_KEY != "tu_clave_assemblyai_aqui" and GROQ_API_KEY != "tu_clave_groq_aqui":
        st.success("✅ APIs configuradas correctamente")
    else:
        st.error("⚠️ Configure las claves API en el código")
        st.code("""
# En la línea 12-13 del código:
ASSEMBLYAI_API_KEY = "tu_clave_aqui"
GROQ_API_KEY = "tu_clave_aqui"
        """)
    
    st.divider()
    
    # Call history section
    st.header("📋 Historial de Llamadas")
    if st.session_state.call_history:
        st.metric("Total de Llamadas Hoy", len(st.session_state.call_history))
        if st.button("Limpiar Historial"):
            st.session_state.call_history = []
            st.session_state.priority_queue = []
            st.rerun()
    else:
        st.info("No hay llamadas procesadas aún")

# Main app
st.title("🚨 Sistema de Transcripción de Emergencias")
st.markdown("### Centro de Despacho 123 - Colombia")

# Priority Queue Dashboard
if st.session_state.priority_queue:
    st.header("🚦 Cola de Prioridad de Emergencias Activas")
    
    # Sort by severity
    severity_order = {'Crítico': 0, 'Alto': 1, 'Medio': 2, 'Bajo': 3}
    sorted_queue = sorted(
        st.session_state.priority_queue,
        key=lambda x: severity_order.get(x.get('severity', 'Bajo'), 4)
    )
    
    for i, call in enumerate(sorted_queue):
        severity_colors = {
            'Crítico': '🔴',
            'Alto': '🟠',
            'Medio': '🟡',
            'Bajo': '🟢'
        }
        
        with st.expander(
            f"{severity_colors.get(call['severity'], '⚪')} Llamada #{call['id']} - {call['type']} - {call['severity']} - {call['time']}"
        ):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.write(f"**Ubicación:** {call.get('location', 'Desconocida')}")
                st.write(f"**Detalles:** {call.get('details', 'N/A')}")
            with col2:
                if st.button(f"✅ Resolver", key=f"resolve_{call['id']}"):
                    st.session_state.priority_queue = [c for c in st.session_state.priority_queue if c['id'] != call['id']]
                    st.rerun()

st.divider()

# Tabs
tab1, tab2 = st.tabs(["📁 Procesar Audio", "📊 Analíticas"])

with tab1:
    uploaded_file = st.file_uploader(
        "Cargar Audio de Emergencia",
        type=['mp3', 'wav', 'm4a', 'flac', 'ogg'],
        help="Formatos soportados: MP3, WAV, M4A, FLAC, OGG"
    )
    
    if uploaded_file is not None:
        st.audio(uploaded_file, format=f'audio/{uploaded_file.name.split(".")[-1]}')
        
        if st.button("🎙️ Procesar Llamada de Emergencia", type="primary", width="stretch"):
            if not st.session_state.get('assemblyai_key') or not st.session_state.get('groq_key'):
                st.error("⚠️ Por favor ingrese ambas claves API en la barra lateral")
            else:
                start_time = datetime.now()
                call_id = len(st.session_state.call_history) + 1
                
                # Transcribe
                st.subheader("📝 Transcripción")
                transcript = transcribe_audio(uploaded_file.getvalue())
                
                if transcript:
                    # Analyze with LLM
                    st.subheader("🤖 Análisis Inteligente")
                    with st.spinner('Analizando llamada con IA...'):
                        llm_analysis = analyze_transcript_with_llm(transcript)
                    
                    if llm_analysis:
                        emotion = llm_analysis.get('emocion', 'CALMA')
                        emotion_icon = llm_analysis.get('icono_emocion', '🟢')
                        palabras_criticas = llm_analysis.get('palabras_criticas', [])
                        severity = llm_analysis.get('severidad_general', 'Medio')
                        emergency_type = llm_analysis.get('tipo_emergencia', 'Otro')
                        justificacion = llm_analysis.get('justificacion', '')
                    else:
                        # Fallback to defaults if LLM fails
                        emotion = "CALMA"
                        emotion_icon = "🟢"
                        palabras_criticas = []
                        severity = "Medio"
                        emergency_type = "Otro"
                        justificacion = "Análisis LLM no disponible"
                    
                    # Alert section
                    if palabras_criticas:
                        st.error("🚨 PALABRAS CRÍTICAS DETECTADAS")
                        alert_cols = st.columns(min(len(palabras_criticas), 4))
                        for i, alert in enumerate(palabras_criticas[:4]):
                            with alert_cols[i]:
                                st.markdown(f"""
                                <div style='background-color:#ff4444;padding:10px;border-radius:5px;text-align:center;color:white;'>
                                    <b>{alert.get('categoria', 'ALERTA').upper()}</b><br/>
                                    {alert.get('palabra', '')}
                                </div>
                                """, unsafe_allow_html=True)
                    
                    # Emotion analysis
                    col_em1, col_em2 = st.columns([1, 3])
                    with col_em1:
                        st.info(f"{emotion_icon} Estado Emocional: **{emotion}**")
                    with col_em2:
                        st.info(f"🎯 Severidad: **{severity}** | Tipo: **{emergency_type}**")
                    
                    if justificacion:
                        st.caption(f"💡 {justificacion}")
                    
                    # Display transcript with highlights
                    st.success("✅ Transcripción completada")
                    highlighted_text = highlight_keywords(transcript, palabras_criticas)
                    st.markdown(highlighted_text, unsafe_allow_html=True)
                    
                    # Extract location
                    location_text = extract_location(transcript)
                    
                    st.divider()
                    
                    # Generate summary
                    st.subheader("📋 Resumen de Emergencia")
                    summary = generate_summary(transcript)
                    
                    if summary:
                        st.success("✅ Resumen generado")
                        st.markdown(summary)
                        
                        st.divider()
                        
                        # Map section - only show if location found
                        if location_text:
                            st.subheader("🗺️ Mapa de Ubicación")
                            st.info(f"📍 Ubicación detectada: **{location_text}**")
                            
                            with st.spinner("Generando mapa..."):
                                coords = geocode_location(location_text)
                                if coords:
                                    try:
                                        emergency_map = create_map(coords[0], coords[1], location_text)
                                        # Use a unique key and return_on_hover=False to prevent reloading
                                        map_data = st_folium(
                                            emergency_map, 
                                            width=700, 
                                            height=400, 
                                            key=f"map_{call_id}_{start_time.timestamp()}",
                                            returned_objects=[]
                                        )
                                    except Exception as e:
                                        st.warning(f"No se pudo mostrar el mapa: {str(e)}")
                                        st.write("Coordenadas:", coords)
                                else:
                                    st.warning(f"No se pudo geocodificar la ubicación: {location_text}")
                        else:
                            st.warning("⚠️ No se detectó ninguna ubicación específica en la llamada")
                        
                        st.divider()
                        
                        # Copy summary button
                        st.button("📋 Copiar Resumen al Portapapeles", width="stretch")
                        
                        # Save to history and priority queue
                        call_record = {
                            'id': call_id,
                            'timestamp': start_time.strftime("%Y-%m-%d %H:%M:%S"),
                            'time': start_time.strftime("%H:%M"),
                            'transcript': transcript,
                            'summary': summary,
                            'location': location_text or "Desconocida",
                            'severity': severity,
                            'type': emergency_type,
                            'alerts': palabras_criticas,
                            'emotion': emotion,
                            'details': transcript[:100] + "...",
                            'justificacion': justificacion
                        }
                        
                        st.session_state.call_history.append(call_record)
                        
                        if severity in ['Crítico', 'Alto']:
                            st.session_state.priority_queue.append(call_record)
                        
                        st.success(f"✅ Llamada #{call_id} procesada y guardada en el historial")

with tab2:
    st.header("📊 Analíticas de Llamadas")
    
    if st.session_state.call_history:
        # Create metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total de Llamadas", len(st.session_state.call_history))
        
        with col2:
            critical_calls = sum(1 for call in st.session_state.call_history if call['severity'] == 'Crítico')
            st.metric("Llamadas Críticas", critical_calls)
        
        with col3:
            high_stress_calls = sum(1 for call in st.session_state.call_history if 'ALTO' in call['emotion'])
            st.metric("Llamadas con Estrés Alto", high_stress_calls)
        
        with col4:
            total_alerts = sum(len(call['alerts']) for call in st.session_state.call_history)
            st.metric("Total de Alertas", total_alerts)
        
        st.divider()
        
        # Call history table
        st.subheader("Historial de Llamadas Recientes")
        df = pd.DataFrame([
            {
                'ID': call['id'],
                'Hora': call['timestamp'],
                'Tipo': call['type'],
                'Severidad': call['severity'],
                'Ubicación': call['location'],
                'Emoción': call['emotion']
            }
            for call in st.session_state.call_history
        ])
        st.dataframe(df, use_container_width=True)
        
        st.divider()
        
        # Detailed view
        st.subheader("Detalles de Llamada")
        selected_call_id = st.selectbox(
            "Seleccionar llamada para ver detalles",
            options=[call['id'] for call in st.session_state.call_history],
            format_func=lambda x: f"Llamada #{x}"
        )
        
        selected_call = next((call for call in st.session_state.call_history if call['id'] == selected_call_id), None)
        
        if selected_call:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Transcripción:**")
                st.text_area("Transcripción completa", selected_call['transcript'], height=200, key=f"detail_transcript_{selected_call_id}", label_visibility="collapsed")
            
            with col2:
                st.markdown("**Resumen:**")
                st.markdown(selected_call['summary'])
                
                if selected_call['alerts']:
                    st.markdown("**Alertas Detectadas:**")
                    for alert in selected_call['alerts']:
                        categoria = alert.get('categoria', 'Alerta')
                        palabra = alert.get('palabra', alert.get('keyword', 'N/A'))
                        st.markdown(f"- ⚠️ {categoria.title()}: {palabra}")
    else:
        st.info("No hay datos de llamadas disponibles aún. Procese algunas llamadas de emergencia para ver analíticas.")

# Footer
st.divider()
st.caption("Sistema de Transcripción de Emergencias Colombia | Solo para propósitos de demostración")