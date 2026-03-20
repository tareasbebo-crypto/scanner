"""
GradeScanner - Data Models
Modelos de datos para el sistema de revisión de notas
"""

from datetime import datetime
from database import db

class Estudiante(db.Model):
    """Modelo de Estudiante"""
    __tablename__ = 'estudiantes'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    carrera = db.Column(db.String(100))
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    examenes = db.relationship('Examen', backref='estudiante', lazy='dynamic')
    notas = db.relationship('Nota', backref='estudiante', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'email': self.email,
            'codigo': self.codigo,
            'carrera': self.carrera,
            'activo': self.activo,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None
        }

class Curso(db.Model):
    """Modelo de Curso"""
    __tablename__ = 'cursos'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    descripcion = db.Column(db.Text)
    profesor = db.Column(db.String(100))
    anno = db.Column(db.Integer, default=datetime.now().year)
    periodo = db.Column(db.String(20))  # Ej: "2024-1", "2024-2"
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    examenes = db.relationship('Examen', backref='curso', lazy='dynamic')
    plantillas = db.relationship('Plantilla', backref='curso', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'codigo': self.codigo,
            'descripcion': self.descripcion,
            'profesor': self.profesor,
            'anno': self.anno,
            'periodo': self.periodo,
            'activo': self.activo
        }

class Examen(db.Model):
    """Modelo de Examen/Evaluación"""
    __tablename__ = 'examenes'
    
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text)
    curso_id = db.Column(db.Integer, db.ForeignKey('cursos.id'), nullable=False)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'))
    plantilla_id = db.Column(db.Integer, db.ForeignKey('plantillas.id'))
    
    # Datos del escaneo
    imagen_path = db.Column(db.String(500))
    texto_ocr = db.Column(db.Text)
    confianza_ocr = db.Column(db.Float)
    
    # Estado y resultados
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, procesado, revisado
    nota_final = db.Column(db.Float)
    observaciones = db.Column(db.Text)
    
    # timestamps
    fecha_escaneo = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_revision = db.Column(db.DateTime)
    
    # Relaciones
    preguntas = db.relationship('Pregunta', backref='examen', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'titulo': self.titulo,
            'descripcion': self.descripcion,
            'curso_id': self.curso_id,
            'estudiante_id': self.estudiante_id,
            'plantilla_id': self.plantilla_id,
            'imagen_path': self.imagen_path,
            'texto_ocr': self.texto_ocr,
            'confianza_ocr': self.confianza_ocr,
            'estado': self.estado,
            'nota_final': self.nota_final,
            'observaciones': self.observaciones,
            'fecha_escaneo': self.fecha_escaneo.isoformat() if self.fecha_escaneo else None,
            'fecha_revision': self.fecha_revision.isoformat() if self.fecha_revision else None,
            'estudiante': self.estudiante.to_dict() if self.estudiante else None,
            'curso': self.curso.to_dict() if self.curso else None
        }

class Plantilla(db.Model):
    """Modelo de Plantilla de Examen"""
    __tablename__ = 'plantillas'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    curso_id = db.Column(db.Integer, db.ForeignKey('cursos.id'), nullable=False)
    
    # Respuestas correctas en formato JSON
    respuestas_correctas = db.Column(db.Text)  # JSON: [{"pregunta": 1, "respuesta": "A", "puntos": 2}, ...]
    
    puntaje_total = db.Column(db.Float, default=0)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    activa = db.Column(db.Boolean, default=True)
    
    # Relaciones
    preguntas = db.relationship('Pregunta', backref='plantilla', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'curso_id': self.curso_id,
            'respuestas_correctas': self.respuestas_correctas,
            'puntaje_total': self.puntaje_total,
            'activa': self.activa,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None
        }

class Pregunta(db.Model):
    """Modelo de Pregunta individual"""
    __tablename__ = 'preguntas'
    
    id = db.Column(db.Integer, primary_key=True)
    examen_id = db.Column(db.Integer, db.ForeignKey('examenes.id'))
    plantilla_id = db.Column(db.Integer, db.ForeignKey('plantillas.id'))
    
    numero = db.Column(db.Integer, nullable=False)
    texto = db.Column(db.Text)
    respuesta_estudiante = db.Column(db.String(10))
    respuesta_correcta = db.Column(db.String(10))
    puntos = db.Column(db.Float, default=0)
    puntos_obtenidos = db.Column(db.Float, default=0)
    
    def to_dict(self):
        return {
            'id': self.id,
            'examen_id': self.examen_id,
            'plantilla_id': self.plantilla_id,
            'numero': self.numero,
            'texto': self.texto,
            'respuesta_estudiante': self.respuesta_estudiante,
            'respuesta_correcta': self.respuesta_correcta,
            'puntos': self.puntos,
            'puntos_obtenidos': self.puntos_obtenidos
        }

class Nota(db.Model):
    """Modelo de Nota/Calificación"""
    __tablename__ = 'notas'
    
    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
    curso_id = db.Column(db.Integer, db.ForeignKey('cursos.id'), nullable=False)
    examen_id = db.Column(db.Integer, db.ForeignKey('examenes.id'))
    
    tipo = db.Column(db.String(50))  # examen, trabajo, proyecto, asistencia
    descripcion = db.Column(db.String(200))
    nota = db.Column(db.Float, nullable=False)
    nota_maxima = db.Column(db.Float, default=10.0)
    porcentaje = db.Column(db.Float)  # Peso en la nota final
    
    fecha_nota = db.Column(db.DateTime, default=datetime.utcnow)
    observaciones = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'estudiante_id': self.estudiante_id,
            'curso_id': self.curso_id,
            'examen_id': self.examen_id,
            'tipo': self.tipo,
            'descripcion': self.descripcion,
            'nota': self.nota,
            'nota_maxima': self.nota_maxima,
            'porcentaje': self.porcentaje,
            'fecha_nota': self.fecha_nota.isoformat() if self.fecha_nota else None,
            'observaciones': self.observaciones
        }

class Configuracion(db.Model):
    """Modelo de Configuración del Sistema"""
    __tablename__ = 'configuracion'
    
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), unique=True, nullable=False)
    valor = db.Column(db.Text)
    descripcion = db.Column(db.String(200))
    
    @staticmethod
    def get_value(clave, default=None):
        config = Configuracion.query.filter_by(clave=clave).first()
        return config.valor if config else default
    
    @staticmethod
    def set_value(clave, valor, descripcion=None):
        config = Configuracion.query.filter_by(clave=clave).first()
        if config:
            config.valor = valor
            if descripcion:
                config.descripcion = descripcion
        else:
            config = Configuracion(clave=clave, valor=valor, descripcion=descripcion)
            db.session.add(config)
        db.session.commit()
