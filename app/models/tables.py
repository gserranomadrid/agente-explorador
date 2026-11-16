import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    nombre = Column(String(150), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Correo(Base):
    __tablename__ = "correos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(String(255), unique=True, nullable=False)
    thread_id = Column(String(255), nullable=False)
    remitente = Column(String(255), nullable=False)
    asunto = Column(Text, nullable=True)
    fecha_recepcion = Column(DateTime(timezone=True), nullable=False)
    cuerpo_texto = Column(Text, nullable=True)
    clasificacion = Column(JSONB, nullable=True)
    estado_procesamiento = Column(String(50), default="PENDIENTE")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Documento(Base):
    __tablename__ = "documentos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correo_id = Column(UUID(as_uuid=True), ForeignKey("correos.id", ondelete="CASCADE"), nullable=False)
    nombre_archivo = Column(String(255), nullable=False)
    tipo_mime = Column(String(100), nullable=False)
    tamanio_bytes = Column(BigInteger, nullable=False)
    hash_sha256 = Column(String(64), unique=True, nullable=False)
    ruta_almacenamiento = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    vector_embedding = Column(Vector(), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ReglaExtraccion(Base):
    __tablename__ = "reglas_extraccion"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    categoria = Column(String(100), nullable=False)
    patron_asunto = Column(String(255), nullable=True)
    patron_remitente = Column(String(255), nullable=True)
    extensiones_permitidas = Column(ARRAY(String), nullable=True)
    prompt_instruccion = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Indicador(Base):
    __tablename__ = "indicadores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    documento_id = Column(UUID(as_uuid=True), ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False)
    categoria = Column(String(100), nullable=False)
    dependencia = Column(String(150), nullable=False)
    metadatos_extraidos = Column(JSONB, nullable=False)
    confianza_clasificacion = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class Evento(Base):
    __tablename__ = "eventos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_evento = Column(String(100), nullable=False)
    origen = Column(String(100), nullable=False)
    detalles = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class MemoriaEpisodica(Base):
    __tablename__ = "memoria_episodica"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correo_id = Column(UUID(as_uuid=True), ForeignKey("correos.id"), nullable=True)
    documento_id = Column(UUID(as_uuid=True), ForeignKey("documentos.id"), nullable=True)
    decision_agente = Column(JSONB, nullable=False)
    correccion_usuario = Column(JSONB, nullable=True)
    fue_correcto = Column(Boolean, default=True)
    retroalimentacion_texto = Column(Text, nullable=True)
    embedding = Column(Vector(), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
