import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go

API_URL = "http://127.0.0.1:8002/api/v1"

st.set_page_config(page_title="Agente Explorador - Dashboard", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
        .stApp { background-color: #F4F7FC; }
        .stApp p:not(.st-c), .stApp label, div[data-testid="metric-container"] div { color: #1E293B; }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        h1, h2, h3 { color: #003366 !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-weight: 600 !important; }
        [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E2E8F0; box-shadow: 2px 0 5px rgba(0,0,0,0.05); }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 { color: #004080 !important; }
        div.stButton > button, div.stButton > button p, div.stButton > button span, div.stButton > button div { background-color: #0056b3 !important; color: #FFFFFF !important; border: none !important; }
        div.stButton > button { border-radius: 6px; padding: 0.5rem 1rem; font-weight: bold; box-shadow: 0 4px 6px rgba(0, 86, 179, 0.2); transition: all 0.3s ease; width: 100%; }
        div.stButton > button:hover { background-color: #003d82 !important; transform: translateY(-1px); }
        ul[data-baseweb="menu"], div[role="listbox"] { background-color: #111827 !important; }
        ul[data-baseweb="menu"] li, ul[data-baseweb="menu"] li span { color: #FFFFFF !important; }
        ul[data-baseweb="menu"] li:hover { background-color: #0056b3 !important; }
        [data-testid="stDataFrame"], [data-testid="stTable"] { background-color: #111827 !important; padding: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.5); }
        [data-testid="stDataFrame"] *, [data-testid="stTable"] * { color: #FFFFFF !important; }
        [data-testid="stAlert"] { border-left: 5px solid #0056b3 !important; }
        [data-testid="stAlert"] * { color: #FFFFFF !important; }
        div[data-testid="metric-container"] { background-color: #FFFFFF; border: 1px solid #E0E6ED; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: transform 0.2s ease; }
        div[data-testid="metric-container"]:hover { transform: translateY(-3px); box-shadow: 0 6px 12px rgba(0,0,0,0.1); }
        div[data-testid="metric-container"] label { color: #5A6A85 !important; font-size: 1.1rem !important; font-weight: 500; }
        div[data-testid="metric-container"] div { color: #0056b3 !important; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: transparent; }
        .stTabs [data-baseweb="tab"] { background-color: #FFFFFF; border-radius: 6px 6px 0 0; padding: 10px 20px; border: 1px solid #E2E8F0; border-bottom: none; box-shadow: 0 -2px 5px rgba(0,0,0,0.02); color: #4A5568; }
        .stTabs [data-baseweb="tab"] p, .stTabs [data-baseweb="tab"] span { color: #4A5568 !important; }
        .stTabs [aria-selected="true"] { background-color: #0056b3 !important; color: #FFFFFF !important; border-color: #0056b3 !important; font-weight: 600; }
        .stTabs [aria-selected="true"] p, .stTabs [aria-selected="true"] span { color: #FFFFFF !important; font-weight: 600; }
        [data-testid="stForm"], [data-testid="stExpander"] { background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
        [data-testid="stExpander"] summary p { color: #004080 !important; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

st.title("🛡️ Agente Explorador de Gmail")
st.markdown("<p style='color: #5A6A85; font-size: 1.2rem; margin-bottom: 2rem;'>Plataforma institucional de inteligencia artificial para clasificación de documentos.</p>", unsafe_allow_html=True)

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2912/2912760.png", width=80) 
    st.header("Panel de Control")
    st.markdown("---")
    
    st.subheader("🌐 Conexión a Gmail")
    try:
        auth_resp = requests.get(f"{API_URL}/auth/status", timeout=10).json()
        if auth_resp.get("authenticated"):
            st.success(f"Conectado como:\n{auth_resp.get('email')}")
        else:
            st.warning("OAuth no activo")
            if auth_resp.get("detail"):
                st.caption(auth_resp["detail"])
            if st.button("🔑 Conectar con Google"):
                with st.spinner("Conectando..."):
                    try:
                        response = requests.get(f"{API_URL}/auth/login", timeout=300)
                        if response.ok:
                            st.rerun()
                        else:
                            detail = response.json().get("detail", response.text)
                            st.error(f"Error: {detail}")
                    except requests.RequestException as exc:
                        st.error(f"Error de red: {exc}")
    except requests.RequestException as exc:
        st.error(f"Backend offline: {exc}")

    st.markdown("---")
    st.subheader("⚙️ Procesamiento")
    if st.button("🔄 Sincronizar Bandeja"):
        with st.spinner("Analizando correos entrantes..."):
            try:
                res = requests.post(f"{API_URL}/emails/sync", timeout=300)
                if res.status_code == 200:
                    data = res.json()
                    st.success(
                        f"**Resumen:**\n"
                        f"- 📥 {data['correos_sincronizados']} Correos procesados\n"
                        f"- 📎 {data['documentos_guardados']} Documentos\n"
                        f"- 🧠 {data['clasificaciones_realizadas']} Clasificados"
                    )
                    if data["errores_clasificacion"]:
                        st.warning(f"Errores: {data['errores_clasificacion']}")
                else:
                    st.error(f"Error {res.status_code}: {res.text}")
            except requests.RequestException as e:
                st.error(f"Error de conexión: {e}")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Visión General",
    "📥 Bandeja de Correos",
    "📄 Repositorio",
    "🧠 Cerebro de IA",
    "⚙️ Logs del Sistema"
])

with tab1:
    col1, col2, col3, col4 = st.columns(4)
    try:
        emails = requests.get(f"{API_URL}/emails/").json()
        docs = requests.get(f"{API_URL}/documents/").json()
        classified = sum(bool(email.get("clasificacion")) for email in emails)
        
        col1.metric("Correos Totales", len(emails))
        col2.metric("Documentos", len(docs))
        col3.metric("Clasificados (IA)", classified)
        col4.metric("Estado del Motor", "En línea")
        st.markdown("<br>", unsafe_allow_html=True)
        
        if emails:
            st.subheader("📈 Análisis de Datos")
            col_chart1, col_chart2 = st.columns(2)
            
            categorias = [e.get("clasificacion", {}).get("categoria", "Pendiente") if e.get("clasificacion") else "Pendiente" for e in emails]
            df_cat = pd.DataFrame(categorias, columns=["Categoría"])
            conteo_cat = df_cat["Categoría"].value_counts()
            
            with col_chart1:
                fig1 = go.Figure(data=[go.Bar(
                    x=conteo_cat.index, y=conteo_cat.values, text=conteo_cat.values, textposition='outside',
                    textfont=dict(size=14, color='#1E293B', family="Arial Black"),
                    marker=dict(color=['#0056b3', '#28a745', '#ffc107', '#dc3545', '#6c757d'], line=dict(color='#002244', width=2.5))
                )])
                fig1.update_layout(
                    title={'text': "<b>Distribución por Categoría</b>", 'x': 0.5, 'xanchor': 'center'},
                    plot_bgcolor='#E9EEF5', paper_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=False, linecolor='#4A5568', linewidth=2, tickfont=dict(color='#1E293B', size=12)),
                    yaxis=dict(showgrid=True, gridcolor='#FFFFFF', gridwidth=2, linecolor='#4A5568', linewidth=2, tickfont=dict(color='#1E293B')),
                    margin=dict(l=20, r=20, t=50, b=20), height=380, font=dict(color='#003366', family="Tahoma, sans-serif")
                )
                st.plotly_chart(fig1, use_container_width=True)
                
            with col_chart2:
                fig2 = go.Figure(data=[go.Bar(
                    x=["Clasificados", "Pendientes"], y=[classified, len(emails) - classified], text=[classified, len(emails) - classified],
                    textposition='outside', textfont=dict(size=14, color='#1E293B', family="Arial Black"),
                    marker=dict(color=['#28a745', '#ffc107'], line=dict(color='#002244', width=2.5)), width=[0.4, 0.4]
                )])
                fig2.update_layout(
                    title={'text': "<b>Estado de Procesamiento</b>", 'x': 0.5, 'xanchor': 'center'},
                    plot_bgcolor='#E9EEF5', paper_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=False, linecolor='#4A5568', linewidth=2, tickfont=dict(color='#1E293B', size=13)),
                    yaxis=dict(showgrid=True, gridcolor='#FFFFFF', gridwidth=2, linecolor='#4A5568', linewidth=2, tickfont=dict(color='#1E293B')),
                    margin=dict(l=20, r=20, t=50, b=20), height=380, font=dict(color='#003366', family="Tahoma, sans-serif")
                )
                st.plotly_chart(fig2, use_container_width=True)

    except Exception:
        col1.metric("Correos Totales", 0)
        col2.metric("Documentos", 0)
        col3.metric("Clasificados (IA)", 0)
        col4.metric("Estado del Motor", "Fuera de línea")
        
with tab2:
    if st.session_state.pop("feedback_notice", None):
        st.success("✅ Retroalimentación registrada en la memoria del agente.")
        
    try:
        emails = requests.get(f"{API_URL}/emails/").json()
        if emails:
            email_rows = []
            for email in emails:
                classification = email.get("clasificacion") or {}
                email_rows.append({
                    "Fecha": email.get("fecha_recepcion", "")[:10],
                    "Remitente": email["remitente"],
                    "Asunto": email["asunto"],
                    "Categoría (IA)": classification.get("categoria", "Pendiente"),
                    "Dependencia": classification.get("dependencia_emisora", ""),
                    "Confianza (%)": f"{(classification.get('nivel_confianza', 0) * 100):.0f}%" if classification.get("nivel_confianza") else "",
                })
            st.dataframe(pd.DataFrame(email_rows), width="stretch", height=300)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("Panel de Corrección Asistida")
            
            email_options = {e["id"]: e for e in emails if e.get("clasificacion")}
            if email_options:
                selected_id = st.selectbox(
                    "Seleccione el registro a inspeccionar:", list(email_options),
                    format_func=lambda x: f"{email_options[x].get('asunto') or 'Sin asunto'} — {email_options[x]['remitente']}"
                )
                current = email_options[selected_id]["clasificacion"]
                categories = ["Financiero", "Académico", "Operativo", "Administrativo", "Indefinido"]
                
                with st.form("classification_feedback"):
                    col_form1, col_form2 = st.columns(2)
                    with col_form1:
                        category = st.selectbox("Categoría Principal", categories, index=categories.index(current["categoria"]) if current["categoria"] in categories else 0)
                        document_type = st.text_input("Clase de Documento", value=current.get("tipo_documento", "No identificado"))
                    with col_form2:
                        dependence = st.text_input("Dependencia / Área", value=current.get("dependencia_emisora", "Desconocida"))
                        period = st.text_input("Periodo Fiscal / Académico", value=current.get("periodo", "No aplica"))
                    
                    st.markdown("---")
                    col_eval1, col_eval2 = st.columns([1, 2])
                    with col_eval1:
                        st.slider("Confianza original", 0.0, 1.0, float(current.get("nivel_confianza", 0.5)), disabled=True)
                    with col_eval2:
                        comment = st.text_input("Notas de revisión")
                        
                    if st.form_submit_button("Confirmar Metadatos"):
                        payload = {
                            "clasificacion": {**current, "categoria": category, "dependencia_emisora": dependence, "tipo_documento": document_type, "periodo": period, "nivel_confianza": float(current.get("nivel_confianza", 0.5))},
                            "comentario": comment or None,
                        }
                        try:
                            requests.post(f"{API_URL}/emails/{selected_id}/feedback", json=payload, timeout=30).raise_for_status()
                            st.session_state["feedback_notice"] = True
                            st.rerun()
                        except requests.RequestException as e:
                            st.error(f"Error guardando: {e}")
            else:
                st.info("No hay correos evaluados.")
        else:
            st.info("Bandeja vacía.")
    except Exception as e:
        st.error(f"Error de lectura: {e}")

with tab3:
    st.subheader("Archivos Institucionales Extraídos")
    try:
        docs = requests.get(f"{API_URL}/documents/").json()
        if docs:
            df_docs = pd.DataFrame(docs)[["nombre_archivo", "tipo_mime", "tamanio_bytes", "hash_sha256"]]
            df_docs.columns = ["Nombre del Archivo", "Formato MIME", "Peso (Bytes)", "Huella Digital (SHA-256)"]
            st.dataframe(df_docs, width="stretch")
        else:
            st.info("Aún no se han extraído adjuntos.")
    except Exception as e:
        st.error(f"Error de lectura: {e}")

with tab4:
    try:
        diag_resp = requests.get(f"{API_URL}/cognition/diagnostics", timeout=10)
        if diag_resp.ok:
            diagnostics = diag_resp.json()
            
            st.subheader("Estado de Procesamiento Local")
            m_col1, m_col2, m_col3 = st.columns(3)
            
            if diagnostics.get("ollama", {}).get("connected"):
                m_col1.success("Backend LLM: Conectado")
            else:
                m_col1.error("Backend LLM: Desconectado")
                
            m_col2.metric("Motor Clasificador", diagnostics.get("models", {}).get("chat", "N/A"))
            m_col3.metric("Motor Vectorial", diagnostics.get("models", {}).get("embedding", "N/A"))
            st.markdown("<br>", unsafe_allow_html=True)
            
            with st.expander("⚙️ Ver Prompt Base del Sistema", expanded=False):
                st.code(diagnostics.get("classification", {}).get("system_prompt", ""), language="markdown")
            
            with st.expander("🛡️ Reglas Institucionales (Overrides)", expanded=False):
                rules = diagnostics.get("active_rules", [])
                if rules:
                    st.dataframe(pd.DataFrame(rules), width="stretch")
                else:
                    st.write("Modo Inferencia Activo (Sin reglas forzadas).")
                
                with st.form("add_rule_form"):
                    st.write("**Nueva Regla Estricta**")
                    r_col1, r_col2 = st.columns(2)
                    r_cat = r_col1.selectbox("Forzar a la Categoría:", ["Financiero", "Académico", "Operativo", "Administrativo", "Indefinido"])
                    r_inst = r_col2.text_input("Directiva para el LLM:")
                    r_subj = r_col1.text_input("Patrón en Asunto:")
                    r_send = r_col2.text_input("Patrón en Remitente:")
                    
                    if st.form_submit_button("Inyectar Regla"):
                        if r_inst:
                            payload = {"category": r_cat, "subject_pattern": r_subj or None, "sender_pattern": r_send or None, "instruction": r_inst}
                            if requests.post(f"{API_URL}/cognition/rules", json=payload).ok:
                                st.success("Regla activada.")
                                st.rerun()
                        else:
                            st.error("Se requiere una directiva escrita.")

            with st.expander("🧠 Explorador de Base Vectorial (Memoria)", expanded=False):
                mem = diagnostics.get("memory", {})
                st.markdown(f"**Registros en el espacio vectorial:** {mem.get('total', 0)} (Corregidos: {mem.get('with_feedback', 0)})")
                
                s_query = st.text_input("Buscar similitud semántica:")
                
                if st.button("Consultar Vectores y Analizar"):
                    if s_query:
                        with st.spinner("Consultando memoria y procesando con el cerebro..."):
                            try:
                                # Consumimos el nuevo endpoint creado en FastAPI
                                r_resp = requests.post(
                                    f"{API_URL}/cognition/rag", 
                                    json={"query": s_query},
                                    timeout=120
                                )
                                
                                if r_resp.status_code == 200:
                                    respuesta_cerebro = r_resp.json().get("respuesta", "Sin respuesta.")
                                    st.markdown("### 🤖 Respuesta del Análisis Cognitivo")
                                    st.info(respuesta_cerebro)
                                else:
                                    st.error(f"Error de la API: {r_resp.status_code} - {r_resp.text}")
                            except requests.RequestException as e:
                                st.error(f"Error de conexión con el backend: {e}")
                    else:
                        st.warning("Por favor, ingresa un término de búsqueda.")
        else:
            st.error("Servicio cognitivo inalcanzable.")
    except Exception as e:
        st.error(f"Error de red: {e}")

with tab5:
    st.subheader("Auditoría Técnica")
    try:
        response = requests.get(f"{API_URL}/events/?limit=100", timeout=10)
        if response.ok:
            events = response.json()
            if events:
                df_events = pd.DataFrame(events)[["created_at", "tipo_evento", "origen", "detalles"]]
                df_events["created_at"] = pd.to_datetime(df_events["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
                df_events.columns = ["Timestamp", "Código de Evento", "Microservicio", "Traza JSON"]
                st.dataframe(df_events, width="stretch", height=400)
            else:
                st.info("Log de auditoría vacío.")
    except requests.RequestException as e:
        st.error(f"Error consultando el log: {e}")