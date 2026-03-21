"""
GradeScanner - Flask Application (Simplified)
Sistema simplificado de examenes con plantillas
Solo examenes: permite registrar plantillas (opcion multiple y opcion libre)
"""

import os
import json
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from database import db, init_app
from config import get_config
from models import Examen, Plantilla, Pregunta, Configuracion, Seccion
from ocr_engine import OCREngine

# Crear aplicación con configuración
app = Flask(__name__)
config = get_config()
app.config.from_object(config)

# Habilitar CORS
CORS(app)

# Configuración de uploads
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

# Inicializar base de datos
init_app(app)

# Asegurar que existe la carpeta de uploads
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Inicializar motor OCR
ocr_engine = OCREngine()


def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# ==================== RUTAS PRINCIPALES ====================

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    """Dashboard principal"""
    return render_template('dashboard.html')


@app.route('/scan')
def scan_page():
    """Página de escaneo"""
    return render_template('scan.html')


@app.route('/secciones')
def secciones_page():
    """Página de gestión de secciones"""
    return render_template('secciones.html')


@app.route('/exams')
def exams_page():
    """Página de exámenes"""
    return render_template('exams.html')


@app.route('/templates')
def templates_page():
    """Página de plantillas"""
    return render_template('templates.html')


# ==================== API: SECCIONES ====================

@app.route('/api/secciones', methods=['GET'])
def get_secciones():
    """Obtiene todas las secciones"""
    secciones = Seccion.query.filter_by(activo=True).all()
    return jsonify([s.to_dict() for s in secciones])


@app.route('/api/secciones', methods=['POST'])
def create_seccion():
    """Crea una nueva sección"""
    data = request.get_json()
    
    seccion = Seccion(
        asignatura=data['asignatura'],
        grado=data['grado'],
        letra=data['letra'],
        lapso=data.get('lapso', ''),
        profesor=data.get('profesor', '')
    )
    
    db.session.add(seccion)
    db.session.commit()
    
    return jsonify(seccion.to_dict()), 201


@app.route('/api/secciones/<int:id>', methods=['GET'])
def get_seccion(id):
    """Obtiene una sección por ID"""
    seccion = Seccion.query.get_or_404(id)
    return jsonify(seccion.to_dict())


@app.route('/api/secciones/<int:id>', methods=['PUT'])
def update_seccion(id):
    """Actualiza una sección"""
    seccion = Seccion.query.get_or_404(id)
    data = request.get_json()
    
    seccion.asignatura = data.get('asignatura', seccion.asignatura)
    seccion.grado = data.get('grado', seccion.grado)
    seccion.letra = data.get('letra', seccion.letra)
    seccion.lapso = data.get('lapso', seccion.lapso)
    seccion.profesor = data.get('profesor', seccion.profesor)
    
    db.session.commit()
    return jsonify(seccion.to_dict())


@app.route('/api/secciones/<int:id>', methods=['DELETE'])
def delete_seccion(id):
    """Elimina (desactiva) una sección"""
    seccion = Seccion.query.get_or_404(id)
    seccion.activo = False
    db.session.commit()
    return jsonify({'message': 'Sección eliminada'})


# ==================== API: PLANTILLAS ====================

@app.route('/api/plantillas', methods=['GET'])
def get_plantillas():
    """Obtiene todas las plantillas"""
    seccion_id = request.args.get('seccion_id', type=int)
    
    query = Plantilla.query.filter_by(activa=True)
    
    if seccion_id:
        query = query.filter_by(seccion_id=seccion_id)
    
    plantillas = query.all()
    return jsonify([p.to_dict() for p in plantillas])


@app.route('/api/plantillas', methods=['POST'])
def create_plantilla():
    """Crea una nueva plantilla"""
    data = request.get_json()
    
    tipo_examen = data.get('tipo_examen', 'multiple_choice')
    
    # Procesar según el tipo
    if tipo_examen == 'multiple_choice':
        respuestas = json.dumps(data.get('respuestas_correctas', []))
        preguntas_texto = None
    else:  # free_response
        respuestas = None
        preguntas_texto = json.dumps(data.get('preguntas_texto', []))
    
    plantilla = Plantilla(
        nombre=data['nombre'],
        descripcion=data.get('descripcion', ''),
        seccion_id=data.get('seccion_id'),
        tipo_examen=tipo_examen,
        respuestas_correctas=respuestas,
        preguntas_texto=preguntas_texto,
        puntaje_total=data.get('puntaje_total', 10)
    )
    
    db.session.add(plantilla)
    db.session.commit()
    
    return jsonify(plantilla.to_dict()), 201


@app.route('/api/plantillas/<int:id>', methods=['GET'])
def get_plantilla(id):
    """Obtiene una plantilla por ID"""
    plantilla = Plantilla.query.get_or_404(id)
    return jsonify(plantilla.to_dict())


@app.route('/api/plantillas/<int:id>', methods=['PUT'])
def update_plantilla(id):
    """Actualiza una plantilla"""
    plantilla = Plantilla.query.get_or_404(id)
    data = request.get_json()
    
    plantilla.nombre = data.get('nombre', plantilla.nombre)
    plantilla.descripcion = data.get('descripcion', plantilla.descripcion)
    if 'seccion_id' in data:
        plantilla.seccion_id = data['seccion_id']
    
    if 'tipo_examen' in data:
        plantilla.tipo_examen = data['tipo_examen']
        if data['tipo_examen'] == 'multiple_choice':
            plantilla.respuestas_correctas = json.dumps(data.get('respuestas_correctas', []))
            plantilla.preguntas_texto = None
        else:
            plantilla.preguntas_texto = json.dumps(data.get('preguntas_texto', []))
            plantilla.respuestas_correctas = None
    
    if 'puntaje_total' in data:
        plantilla.puntaje_total = data['puntaje_total']
    
    db.session.commit()
    return jsonify(plantilla.to_dict())


@app.route('/api/plantillas/<int:id>', methods=['DELETE'])
def delete_plantilla(id):
    """Elimina (desactiva) una plantilla"""
    plantilla = Plantilla.query.get_or_404(id)
    plantilla.activa = False
    db.session.commit()
    return jsonify({'message': 'Plantilla eliminada'})


# ==================== API: EXÁMENES Y ESCANEO ====================

@app.route('/api/scan', methods=['POST'])
def scan_examen():
    """Escanea un examen desde una imagen"""
    if 'file' not in request.files:
        return jsonify({'error': 'No se recibió ningún archivo'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
    
    if file and allowed_file(file.filename):
        # Generar nombre único para el archivo
        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        titulo = request.form.get('titulo', 'Examen sin título')
        seccion_id = request.form.get('seccion_id', type=int)
        plantilla_id = request.form.get('plantilla_id', type=int)
        
        # Procesar OCR
        try:
            # Obtener plantilla
            plantilla = None
            tipo_examen = 'multiple_choice'
            if plantilla_id:
                plantilla = Plantilla.query.get(plantilla_id)
                if plantilla:
                    tipo_examen = plantilla.tipo_examen
            
            # Procesar imagen
            result = ocr_engine.extract_text_with_confidence(filepath)
            
            # Extraer respuestas según el tipo de plantilla
            if tipo_examen == 'multiple_choice':
                extracted_answers = ocr_engine.extract_answers(result['text'])
            else:
                # Para opción libre, extraer texto completo
                extracted_answers = ocr_engine.extract_free_text(result['text'])
            
            # Crear examen en la base de datos
            examen = Examen(
                titulo=titulo,
                seccion_id=seccion_id,
                plantilla_id=plantilla_id,
                imagen_path=f"/uploads/{filename}",
                texto_ocr=result['text'],
                confianza_ocr=result['confidence'],
                estado='procesado' if plantilla else 'pendiente'
            )
            
            db.session.add(examen)
            db.session.commit()
            
            # Calificar si hay plantilla
            grade_result = None
            if plantilla:
                if tipo_examen == 'multiple_choice':
                    correct_answers = json.loads(plantilla.respuestas_correctas) if plantilla.respuestas_correctas else []
                    grade_result = ocr_engine.grade_answers(extracted_answers, correct_answers)
                else:
                    # Opción libre - grading por palabras clave
                    preguntas = json.loads(plantilla.preguntas_texto) if plantilla.preguntas_texto else []
                    grade_result = ocr_engine.grade_free_response(extracted_answers, preguntas)
                
                examen.nota_final = grade_result['nota']
                examen.estado = 'revisado'
                
                # Crear preguntas
                for r in grade_result['resultados']:
                    pregunta = Pregunta(
                        examen_id=examen.id,
                        plantilla_id=plantilla_id,
                        numero=r['pregunta'],
                        tipo=tipo_examen,
                        respuesta_estudiante=r.get('respuesta_estudiante'),
                        respuesta_correcta=r.get('respuesta_correcta'),
                        respuesta_texto=r.get('respuesta_texto'),
                        respuesta_esperada=r.get('respuesta_esperada'),
                        coincidencias=r.get('coincidencias'),
                        puntos=r['puntos'],
                        puntos_obtenidos=r['puntos_obtenidos']
                    )
                    db.session.add(pregunta)
                
                db.session.commit()
            
            return jsonify({
                'examen': examen.to_dict(),
                'ocr': {
                    'text': result['text'],
                    'confidence': result['confidence'],
                    'words': result['words']
                },
                'extracted_answers': extracted_answers,
                'grade': grade_result
            })
            
        except Exception as e:
            return jsonify({'error': f'Error al procesar: {str(e)}'}), 500
    
    return jsonify({'error': 'Tipo de archivo no permitido'}), 400


@app.route('/api/examenes', methods=['GET'])
def get_examenes():
    """Obtiene todos los exámenes"""
    seccion_id = request.args.get('seccion_id', type=int)
    plantilla_id = request.args.get('plantilla_id', type=int)
    estado = request.args.get('estado')
    
    query = Examen.query
    
    if seccion_id:
        query = query.filter_by(seccion_id=seccion_id)
    if plantilla_id:
        query = query.filter_by(plantilla_id=plantilla_id)
    if estado:
        query = query.filter_by(estado=estado)
    
    examenes = query.order_by(Examen.fecha_escaneo.desc()).all()
    return jsonify([e.to_dict() for e in examenes])


@app.route('/api/examenes/<int:id>', methods=['GET'])
def get_examen(id):
    """Obtiene un examen por ID"""
    examen = Examen.query.get_or_404(id)
    
    # Obtener preguntas del examen
    preguntas = Pregunta.query.filter_by(examen_id=id).all()
    
    result = examen.to_dict()
    result['preguntas'] = [p.to_dict() for p in preguntas]
    
    return jsonify(result)


@app.route('/api/examenes/<int:id>', methods=['PUT'])
def update_examen(id):
    """Actualiza un examen (nota manual, observaciones)"""
    examen = Examen.query.get_or_404(id)
    data = request.get_json()
    
    if 'nota_final' in data:
        examen.nota_final = data['nota_final']
    if 'observaciones' in data:
        examen.observaciones = data['observaciones']
    if 'estado' in data:
        examen.estado = data['estado']
    
    if data.get('estado') == 'revisado':
        examen.fecha_revision = datetime.utcnow()
    
    db.session.commit()
    return jsonify(examen.to_dict())


@app.route('/api/examenes/<int:id>', methods=['DELETE'])
def delete_examen(id):
    """Elimina un examen"""
    examen = Examen.query.get_or_404(id)
    db.session.delete(examen)
    db.session.commit()
    return jsonify({'message': 'Examen eliminado'})


# ==================== API: PREGUNTAS ====================

@app.route('/api/preguntas/examen/<int:examen_id>', methods=['GET'])
def get_preguntas_examen(examen_id):
    """Obtiene las preguntas de un examen"""
    preguntas = Pregunta.query.filter_by(examen_id=examen_id).order_by(Pregunta.numero).all()
    return jsonify([p.to_dict() for p in preguntas])


# ==================== API: ESTADÍSTICAS ====================

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Obtiene estadísticas del sistema"""
    
    # Contar secciones
    total_secciones = Seccion.query.filter_by(activo=True).count()
    
    # Contar plantillas
    total_plantillas = Plantilla.query.filter_by(activa=True).count()
    
    # Contar exámenes
    total_examenes = Examen.query.count()
    
    # Exámenes por estado
    examen_estados = db.session.query(
        Examen.estado, 
        db.func.count(Examen.id)
    ).group_by(Examen.estado).all()
    
    # Promedio de notas
    notas_promedio = db.session.query(
        db.func.avg(Examen.nota_final)
    ).filter(Examen.nota_final.isnot(None)).scalar() or 0
    
    # Exámenes recientes
    examenes_recientes = Examen.query.order_by(
        Examen.fecha_escaneo.desc()
    ).limit(10).all()
    
    return jsonify({
        'total_secciones': total_secciones,
        'total_plantillas': total_plantillas,
        'total_examenes': total_examenes,
        'examenes_por_estado': {e[0]: e[1] for e in examen_estados},
        'nota_promedio': round(float(notas_promedio), 2),
        'examenes_recientes': [e.to_dict() for e in examenes_recientes]
    })


# ==================== API: SALUD ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint de verificación de salud"""
    return jsonify({
        'status': 'ok',
        'environment': config.ENV,
        'database': 'supabase' if config.USE_SUPABASE else 'sqlite'
    })


# ==================== ARCHIVOS ESTÁTICOS ====================

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Recurso no encontrado'}), 404
