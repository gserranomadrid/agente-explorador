import pandas as pd
import requests
import streamlit as st

API_URL = "http://127.0.0.1:8002/api/v1"

st.set_page_config(page_title="Agente Explorador - Dashboard", layout="wide")
st.title("?? Agente Explorador de Gmail - Panel Inicial")

st.sidebar.header("Conectividad y Acciones")
try:
    auth_resp = requests.get(f"{API_URL}/auth/status").json()
    if auth_resp.get("authenticated"):
        st.sidebar.success(f"Conectado: {auth_resp.get('email')}")
    else:
        st.sidebar.warning("OAuth no activo")
        if st.sidebar.button("Autenticar con Google"):
            requests.get(f"{API_URL}/auth/login")
            st.rerun()
except Exception:
    st.sidebar.error("Backend offline (FastAPI no responde)")

if st.sidebar.button("🔄 Sincronizar Bandeja Gmail"):
    with st.spinner("Sincronizando correos..."):
        try:
            res = requests.post(f"{API_URL}/emails/sync")
            if res.status_code == 200:
                data = res.json()
                st.sidebar.success(f"Sincronizados: {data.get('correos_sincronizados', 0)}")
            else:
                st.sidebar.error(f"Error {res.status_code}: {res.text}")
        except Exception as e:
            st.sidebar.error(f"Excepción de conexión: {e}")
            
tab1, tab2, tab3 = st.tabs(["?? M?tricas", "?? Historial de Correos", "?? Documentos y Adjuntos"])

with tab1:
    st.subheader("M?tricas del Sistema")
    col1, col2, col3 = st.columns(3)
    try:
        emails = requests.get(f"{API_URL}/emails/").json()
        docs = requests.get(f"{API_URL}/documents/").json()
        col1.metric("Total Correos", len(emails))
        col2.metric("Total Documentos", len(docs))
        col3.metric("Estado Backend", "Operativo ??")
    except Exception:
        col1.metric("Total Correos", 0)
        col2.metric("Total Documentos", 0)
        col3.metric("Estado Backend", "Desconectado ??")

with tab2:
    st.subheader("Correos Procesados")
    try:
        emails = requests.get(f"{API_URL}/emails/").json()
        if emails:
            st.dataframe(
                pd.DataFrame(emails)[
                    ["remitente", "asunto", "estado_procesamiento", "fecha_recepcion"]
                ],
                width="stretch",
            )
        else:
            st.info("No hay correos registrados.")
    except Exception as e:
        st.error(f"Error cargando correos: {e}")

with tab3:
    st.subheader("Documentos Guardados (con Hash SHA-256)")
    try:
        docs = requests.get(f"{API_URL}/documents/").json()
        if docs:
            st.dataframe(
                pd.DataFrame(docs)[
                    ["nombre_archivo", "tipo_mime", "tamanio_bytes", "hash_sha256"]
                ],
                width="stretch",
            )
        else:
            st.info("No hay documentos almacenados.")
    except Exception as e:
        st.error(f"Error cargando documentos: {e}")
