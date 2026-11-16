import pandas as pd
import requests
import streamlit as st

API_URL = "http://127.0.0.1:8002/api/v1"

# Configuración de página - Título y layout
st.set_page_config(page_title="Agente Explorador - Dashboard", page_icon="🤖", layout="wide")

# Estilos personalizados básicos (opcional, para mejorar márgenes)
st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🤖 Agente Explorador de Gmail - Panel Inicial")
st.markdown("Plataforma inteligente de clasificación y extracción de documentos institucionales.")
st.divider()

# ==========================================
# SIDEBAR: Conectividad y Acciones
# ==========================================
with st.sidebar:
    st.header("⚙️ Panel de Control")
    
    # Bloque de Autenticación
    st.subheader("Conexión a Gmail")
    try:
        auth_resp = requests.get(f"{API_URL}/auth/status", timeout=10).json()
        if auth_resp.get("authenticated"):
            st.success(f"✅ Conectado:\n{auth_resp.get('email')}")
        else:
            st.warning("⚠️ OAuth no activo")
            if auth_resp.get("detail"):
                st.caption(auth_resp["detail"])
            if st.button("🔑 Autenticar con Google", width="stretch"):
                with st.spinner("Esperando autorización..."):
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

    st.divider()

    # Bloque de Sincronización
    st.subheader("Acciones del Agente")
    if st.button("🔄 Sincronizar Bandeja Ahora", type="primary", width="stretch"):
        with st.spinner("Sincronizando y analizando correos..."):
            try:
                res = requests.post(f"{API_URL}/emails/sync", timeout=300)
                if res.status_code == 200:
                    data = res.json()
                    st.success(
                        f"**Resumen de Sincronización:**\n\n"
                        f"- 📥 Sincronizados: {data['correos_sincronizados']} (Nuevos: {data['nuevos']})\n"
                        f"- 📎 Adjuntos guardados: {data['documentos_guardados']}\n"
                        f"- 🧠 Clasificados por IA: {data['clasificaciones_realizadas']}"
                    )
                    if data.get("errores_clasificacion"):
                        st.warning(
                            f"Pendientes de clasificación: {data['errores_clasificacion']}. "
                            f"{'; '.join(data.get('detalle_errores_clasificacion', []))}"
                        )
                else:
                    st.error(f"Error {res.status_code}: {res.text}")
            except requests.RequestException as e:
                st.error(f"Excepción de conexión: {e}")

    if st.button("🧠 Clasificar correos pendientes", width="stretch"):
        try:
            emails_response = requests.get(f"{API_URL}/emails/", timeout=30)
            emails_response.raise_for_status()
            emails = emails_response.json()
            pending_count = sum(not email.get("clasificacion") for email in emails)

            if pending_count == 0:
                st.info("No hay correos pendientes de clasificación.")
            else:
                progress = st.progress(0.0)
                classified_count = 0
                errors = []
                for index in range(pending_count):
                    progress.progress(
                        index / pending_count,
                        text=f"Clasificando correo {index + 1} de {pending_count}...",
                    )
                    response = requests.post(
                        f"{API_URL}/emails/classify-pending",
                        params={"limit": 1},
                        timeout=300,
                    )
                    if response.status_code != 200:
                        st.error(f"Error {response.status_code}: {response.text}")
                        break

                    result = response.json()
                    if result["pendientes_encontrados"] == 0:
                        break
                    classified_count += result["clasificaciones_realizadas"]
                    if result["errores_clasificacion"]:
                        errors.extend(result["detalle_errores_clasificacion"])
                        break
                    progress.progress(
                        (index + 1) / pending_count,
                        text=(
                            f"Clasificados {classified_count} de "
                            f"{pending_count} correos."
                        ),
                    )

                if classified_count:
                    st.success(f"Clasificados {classified_count} correos.")
                if errors:
                    st.error("Error clasificando: " + "; ".join(errors))
                elif classified_count == 0:
                    st.warning("No se pudo clasificar ningún correo.")
        except requests.RequestException as exc:
            st.error(f"Error al clasificar los pendientes: {exc}")

# ==========================================
# ÁREA PRINCIPAL: Pestañas de Navegación
# ==========================================
tab_metrics, tab_emails, tab_docs, tab_agent, tab_logs = st.tabs([
    "📊 Dashboard",
    "📥 Correos Procesados",
    "📄 Documentos y Adjuntos",
    "🧠 Diagnóstico del Agente",
    "⚙️ Visor de Eventos"
])

# --- PESTAÑA 1: MÉTRICAS ---
with tab_metrics:
    st.subheader("Visión General del Sistema")
    col1, col2, col3, col4 = st.columns(4)
    try:
        emails = requests.get(f"{API_URL}/emails/").json()
        docs = requests.get(f"{API_URL}/documents/").json()
        classified = sum(bool(email.get("clasificacion")) for email in emails)
        
        col1.metric("Total Correos Ingestados", len(emails), delta="Actualizado")
        col2.metric("Documentos Extraídos", len(docs))
        col3.metric("Clasificados por IA", classified)
        col4.metric("Estado Backend", "🟢 Operativo")
    except Exception:
        col1.metric("Total Correos", 0)
        col2.metric("Total Documentos", 0)
        col3.metric("Correos clasificados", 0)
        col4.metric("Estado Backend", "🔴 Desconectado")

# --- PESTAÑA 2: CORREOS Y RETROALIMENTACIÓN ---
with tab_emails:
    st.subheader("Bandeja de Procesamiento")
    
    if st.session_state.pop("feedback_notice", None):
        st.success("✅ Retroalimentación registrada y enviada al agente exitosamente.")
        
    try:
        # Cargar tabla de correos
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
                    "Confianza": f"{classification.get('nivel_confianza', 0):.2f}" if classification.get("nivel_confianza") else "",
                    "Estado": email["estado_procesamiento"],
                })
            st.dataframe(pd.DataFrame(email_rows), width="stretch", height=250)

            st.divider()

            # Sección de revisión humana (Human-in-the-loop)
            st.subheader("🧑‍🏫 Interfaz de Corrección (Human-in-the-Loop)")
            st.markdown("Ayuda al agente a aprender corrigiendo o aprobando sus decisiones.")
            
            email_options = {e["id"]: e for e in emails if e.get("clasificacion")}
            
            if email_options:
                selected_id = st.selectbox(
                    "Selecciona un correo para revisar:",
                    list(email_options.keys()),
                    format_func=lambda x: f"{email_options[x].get('asunto') or 'Sin asunto'} — {email_options[x]['remitente']}"
                )
                
                selected_email = email_options[selected_id]
                current = selected_email["clasificacion"]
                categories = ["Financiero", "Académico", "Operativo", "Administrativo", "Indefinido"]
                
                with st.form("classification_feedback", clear_on_submit=False):
                    st.markdown("**Metadatos Extraídos por el Agente:**")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        category = st.selectbox(
                            "Categoría",
                            categories,
                            index=categories.index(current["categoria"]) if current["categoria"] in categories else 0,
                        )
                        document_type = st.text_input("Tipo de documento", value=current.get("tipo_documento", ""))
                    
                    with col2:
                        dependence = st.text_input("Dependencia emisora", value=current.get("dependencia_emisora", ""))
                        period = st.text_input("Periodo", value=current.get("periodo", ""))
                    
                    st.markdown("**Evaluación de la Decisión:**")
                    conf_col, comm_col = st.columns([1, 2])
                    with conf_col:
                        confidence = st.slider(
                            "Confianza reportada por IA",
                            min_value=0.0, max_value=1.0, 
                            value=float(current.get("nivel_confianza", 0.5)),
                            disabled=True # El humano no edita la confianza de la IA, solo la ve
                        )
                    with comm_col:
                        comment = st.text_input("Nota o comentario (para memoria del modelo)")
                    
                    submit_col1, submit_col2 = st.columns([1, 3])
                    with submit_col1:
                        submitted = st.form_submit_button("Guardar y Entrenar IA", type="primary")

                    if submitted:
                        payload = {
                            "clasificacion": {
                                **current,
                                "categoria": category,
                                "dependencia_emisora": dependence,
                                "tipo_documento": document_type,
                                "periodo": period,
                                "nivel_confianza": float(current.get("nivel_confianza", 1.0)),
                            },
                            "comentario": comment or None,
                        }
                        try:
                            f_res = requests.post(f"{API_URL}/emails/{selected_id}/feedback", json=payload, timeout=30)
                            f_res.raise_for_status()
                            st.session_state["feedback_notice"] = True
                            st.rerun()
                        except requests.RequestException as e:
                            st.error(f"Error guardando retroalimentación: {e}")
            else:
                st.info("No hay correos clasificados disponibles para revisión.")
        else:
            st.info("Bandeja vacía. Sincroniza correos para empezar.")
    except Exception as e:
        st.error(f"Error cargando correos: {e}")

# --- PESTAÑA 3: DOCUMENTOS ---
with tab_docs:
    st.subheader("Gestión de Documentos Adjuntos")
    try:
        docs = requests.get(f"{API_URL}/documents/").json()
        if docs:
            df_docs = pd.DataFrame(docs)[["nombre_archivo", "tipo_mime", "tamanio_bytes", "hash_sha256"]]
            df_docs.columns = ["Nombre del Archivo", "Tipo (MIME)", "Tamaño (Bytes)", "Firma SHA-256"]
            st.dataframe(df_docs, width="stretch")
        else:
            st.info("No se han extraído documentos adjuntos aún.")
    except Exception as e:
        st.error(f"Error cargando documentos: {e}")

# --- PESTAÑA 4: AGENTE COGNITIVO ---
with tab_agent:
    st.subheader("Cerebro del Agente Cognitivo")
    st.markdown("Supervisa la conexión local de Ollama, reglas de inferencia y la memoria vectorial.")
    
    try:
        diag_res = requests.get(f"{API_URL}/cognition/diagnostics", timeout=10)
        diag_res.raise_for_status()
        diagnostics = diag_res.json()
        
        # 1. Estado de los Modelos (Tarjetas visuales)
        st.markdown("#### 🔌 Conexión Local (Ollama)")
        ollama = diagnostics["ollama"]
        
        m_col1, m_col2, m_col3 = st.columns(3)
        if ollama["connected"]:
            m_col1.success("Servidor Ollama: En línea")
        else:
            m_col1.error(f"Servidor Ollama: Caído ({ollama.get('error', '')})")
            
        chat_status = "🟢 Disponible" if ollama["chat_model_available"] else "🔴 No descargado"
        embed_status = "🟢 Disponible" if ollama["embedding_model_available"] else "🔴 No descargado"
        
        m_col2.metric("Modelo Clasificador", diagnostics["models"]["chat"], chat_status)
        m_col3.metric("Modelo Embeddings", diagnostics["models"]["embedding"], embed_status)
        
        # 2. Configuración e Instrucciones
        with st.expander("📝 System Prompt y Umbrales", expanded=False):
            st.code(diagnostics["classification"]["system_prompt"], language="markdown")
            st.caption(
                f"Búsqueda Few-Shot activada con confianza ≤ {diagnostics['classification']['few_shot_threshold']:.2f}. "
                f"Límite de ejemplos inyectados: {diagnostics['classification']['max_similar_examples']}."
            )

        # 3. Reglas Institucionales
        with st.expander("🛠️ Reglas Institucionales Activas", expanded=True):
            rules = diagnostics["active_rules"]
            if rules:
                st.dataframe(pd.DataFrame(rules), width="stretch", hide_index=True)
            else:
                st.info("El agente actualmente toma decisiones basadas solo en el prompt base.")
            
            st.markdown("**Crear Nueva Regla Estricta**")
            with st.form("create_extraction_rule", clear_on_submit=True):
                r_col1, r_col2, r_col3 = st.columns(3)
                rule_category = r_col1.selectbox("Categoría Forzada", ["Financiero", "Académico", "Operativo", "Administrativo", "Indefinido"])
                subject_pattern = r_col2.text_input("Asunto contiene (Opcional)")
                sender_pattern = r_col3.text_input("Remitente contiene (Opcional)")
                
                rule_instruction = st.text_area("Instrucción detallada para el LLM", height=100)
                
                if st.form_submit_button("➕ Agregar Regla al Sistema"):
                    if not rule_instruction.strip():
                        st.error("La instrucción no puede estar vacía.")
                    else:
                        payload = {
                            "category": rule_category,
                            "subject_pattern": subject_pattern or None,
                            "sender_pattern": sender_pattern or None,
                            "instruction": rule_instruction,
                        }
                        r_resp = requests.post(f"{API_URL}/cognition/rules", json=payload, timeout=10)
                        if r_resp.status_code == 201:
                            st.success("Regla añadida correctamente.")
                            st.rerun()
                        else:
                            st.error(f"Error guardando regla: {r_resp.text}")

        # 4. Memoria Vectorial y Búsqueda
        with st.expander("🧠 Búsqueda Semántica en Memoria Episódica", expanded=False):
            memory = diagnostics["memory"]
            st.markdown(f"**Base Vectorial:** {memory['total']} episodios almacenados ({memory['with_feedback']} con feedback humano).")
            
            st.markdown("Prueba de búsqueda vectorial (Busca situaciones pasadas similares):")
            with st.form("semantic_memory_search"):
                search_query = st.text_input("Ingresa un texto o asunto de prueba:")
                search_submitted = st.form_submit_button("🔍 Buscar Ejemplos Similares")

            if search_submitted and search_query.strip():
                try:
                    s_resp = requests.post(f"{API_URL}/cognition/search", json={"query": search_query}, timeout=120)
                    s_resp.raise_for_status()
                    results = s_resp.json()
                    
                    if results.get("results"):
                        search_rows = []
                        for item in results["results"]:
                            cls_data = item.get("classification") or {}
                            search_rows.append({
                                "Similitud": f"{item['similarity']:.2f}",
                                "Categoría Enseñada": cls_data.get("categoria", ""),
                                "Documento": cls_data.get("tipo_documento", ""),
                                "Feedback Correcto": "✅" if item["was_correct"] else "❌"
                            })
                        st.dataframe(pd.DataFrame(search_rows), width="stretch", hide_index=True)
                    else:
                        st.warning("No se encontraron ejemplos cercanos en el espacio vectorial.")
                except Exception as e:
                    st.error(f"Fallo en búsqueda semántica: {e}")

    except requests.RequestException as exc:
        st.error(f"No se pudo cargar el módulo cognitivo: {exc}")

# --- PESTAÑA 5: EVENT LOGS ---
with tab_logs:
    st.subheader("Auditoría y Trazabilidad")
    try:
        response = requests.get(f"{API_URL}/events/?limit=100", timeout=10)
        response.raise_for_status()
        events = response.json()
        if events:
            df_events = pd.DataFrame(events)[["created_at", "tipo_evento", "origen", "detalles"]]
            df_events["created_at"] = pd.to_datetime(df_events["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            df_events.columns = ["Marca de Tiempo", "Tipo de Evento", "Módulo Origen", "Detalles Técnicos"]
            st.dataframe(df_events, width="stretch", height=400)
        else:
            st.info("El log de auditoría está vacío.")
    except requests.RequestException as e:
        st.error(f"Error conectando al sistema de logs: {e}")