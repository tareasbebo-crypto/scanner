"""
GradeScanner - Flask Application
Servidor principal de la aplicación de revisión de notas
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
from models import Estudiante, Curso, Examen, Plantilla, Pregunta, Nota, Configuracion
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


@app.route('/students')
def students_page():
    """Página de gestión de estudiantes"""
    return render_template('students.html')


@app.route('/courses')
def courses_page():
    """Página de gestión de cursos"""
    return render_template('courses.html')


@app.route('/exams')
def exams_page():
    """Página de exámenes"""
    return render_template('exams.html')


@app.route('/templates')
def templates_page():
    """Página de plantillas"""
    return render_template('templates.html')


@app.route('/reports')
def reports_page():
    """Página de reportes"""
    return render_template('reports.html')


# ==================== API: ESTUDIANTES ====================

@app.route('/api/estudiantes', methods=['GET'])
def get_estudiantes():
    """Obtiene todos los estudiantes"""
    estudiantes = Estudiante.query.filter_by(activo=True).all()
    return jsonify([e.to_dict() for e in estudiantes])


@app.route('/api/estudiantes', methods=['POST'])
def create_estudiante():
    """Crea un nuevo estudiante"""
    data = request.get_json()
    
    estudiante = Estudiante(
        nombre=data['nombre'],
        apellido=data['apellido'],
        email=data['email'],
        codigo=data['codigo'],
        carrera=data.get('carrera', '')
    )
    
    db.session.add(estudiante)
    db.session.commit()
    
    return jsonify(estudiante.to_dict()), 201


@app.route('/api/estudiantes/<int:id>', methods=['GET'])
def get_estudiante(id):
    """Obtiene un estudiante por ID"""
    estudiante = Estudiante.query.get_or_404(id)
    return jsonify(estudiante.to_dict())


@app.route('/api/estudiantes/<int:id>', methods=['PUT'])
def update_estudiante(id):
    """Actualiza un estudiante"""
    estudiante = Estudiante.query.get_or_404(id)
    data = request.get_json()
    
    estudiante.nombre = data.get('nombre', estudiante.nombre)
    estudiante.apellido = data.get('apellido', estudiante.apellido)
    estudiante.email = data.get('email', estudiante.email)
    estudiante.codigo = data.get('codigo', estudiante.codigo)
    estudiante.carrera = data.get('carrera', estudiante.carrera)
    
    db.session.commit()
    return jsonify(estudiante.to_dict())


@app.route('/api/estudiantes/<int:id>', methods=['DELETE'])
def delete_estudiante(id):
    """Elimina (desactiva) un estudiante"""
    estudiante = Estudiante.query.get_or_404(id)
    estudiante.activo = False
    db.session.commit()
    return jsonify({'message': 'Estudiante eliminado'})


# ==================== API: CURSOS ====================

@app.route('/api/cursos', methods=['GET'])
def get_cursos():
    """Obtiene todos los cursos"""
    cursos = Curso.query.filter_by(activo=True).all()
    return jsonify([c.to_dict() for c in cursos])


@app.route('/api/cursos', methods=['POST'])
def create_curso():
    """Crea un nuevo curso"""
    data = request.get_json()
    
    curso = Curso(
        nombre=data['nombre'],
        codigo=data['codigo'],
        descripcion=data.get('descripcion', ''),
        profesor=data.get('profesor', ''),
        anno=data.get('anno', datetime.now().year),
        periodo=data.get('periodo', '')
    )
    
    db.session.add(curso)
    db.session.commit()
    
    return jsonify(curso.to_dict()), 201


@app.route('/api/cursos/<int:id>', methods=['GET'])
def get_curso(id):
    """Obtiene un curso por ID"""
    curso = Curso.query.get_or_404(id)
    return jsonify(curso.to_dict())


@app.route('/api/cursos/<int:id>', methods=['PUT'])
def update_curso(id):
    """Actualiza un curso"""
    curso = Curso.query.get_or_404(id)
    data = request.get_json()
    
    curso.nombre = data.get('nombre', curso.nombre)
    curso.codigo = data.get('codigo', curso.codigo)
    curso.descripcion = data.get('descripcion', curso.descripcion)
    curso.profesor = data.get('profesor', curso.profesor)
    curso.periodo = data.get('periodo', curso.periodo)
    
    db.session.commit()
    return jsonify(curso.to_dict())


# ==================== API: PLANTILLAS ====================

@app.route('/api/plantillas', methods=['GET'])
def get_plantillas():
    """Obtiene todas las plantillas"""
    plantillas = Plantilla.query.filter_by(activa=True).all()
    return jsonify([p.to_dict() for p in plantillas])


@app.route('/api/plantillas', methods=['POST'])
def create_plantilla():
    """Crea una nueva plantilla"""
    data = request.get_json()
    
    respuestas = json.dumps(data.get('respuestas_correctas', []))
    
    plantilla = Plantilla(
        nombre=data['nombre'],
        descripcion=data.get('descripcion', ''),
        curso_id=data['curso_id'],
        respuestas_correctas=respuestas,
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
        
        # Datos adicionales del formulario
        curso_id = request.form.get('curso_id', type=int)
        titulo = request.form.get('titulo', 'Examen sin título')
        plantilla_id = request.form.get('plantilla_id', type=int)
        
        # Procesar OCR
        try:
            # Obtener respuestas correctas si hay plantilla
            correct_answers = []
            if plantilla_id:
                plantilla = Plantilla.query.get(plantilla_id)
                if plantilla and plantilla.respuestas_correctas:
                    correct_answers = json.loads(plantilla.respuestas_correctas)
            
            # Procesar imagen
            result = ocr_engine.extract_text_with_confidence(filepath)
            extracted_answers = ocr_engine.extract_answers(result['text'])
            student_code = ocr_engine.detect_student_code(result['text'])
            
            # Crear examen en la base de datos
            examen = Examen(
                titulo=titulo,
                curso_id=curso_id,
                plantilla_id=plantilla_id,
                imagen_path=f"/uploads/{filename}",
                texto_ocr=result['text'],
                confianza_ocr=result['confidence'],
                estado='procesado' if correct_answers else 'pendiente'
            )
            
            # Buscar estudiante por código
            if student_code:
                estudiante = Estudiante.query.filter_by(codigo=student_code).first()
                if estudiante:
                    examen.estudiante_id = estudiante.id
            
            db.session.add(examen)
            db.session.commit()
            
            # Calificar si hay respuestas correctas
            grade_result = None
            if correct_answers:
                grade_result = ocr_engine.grade_answers(extracted_answers, correct_answers)
                examen.nota_final = grade_result['nota']
                examen.estado = 'revisado'
                
                # Crear preguntas
                for r in grade_result['resultados']:
                    pregunta = Pregunta(
                        examen_id=examen.id,
                        plantilla_id=plantilla_id,
                        numero=r['pregunta'],
                        respuesta_estudiante=r['respuesta_estudiante'],
                        respuesta_correcta=r['respuesta_correcta'],
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
                'student_code': student_code,
                'grade': grade_result
            })
            
        except Exception as e:
            return jsonify({'error': f'Error al procesar: {str(e)}'}), 500
    
    return jsonify({'error': 'Tipo de archivo no permitido'}), 400


@app.route('/api/examenes', methods=['GET'])
def get_examenes():
    """Obtiene todos los exámenes"""
    curso_id = request.args.get('curso_id', type=int)
    estado = request.args.get('estado')
    
    query = Examen.query
    
    if curso_id:
        query = query.filter_by(curso_id=curso_id)
    if estado:
        query = query.filter_by(estado=estado)
    
    examenes = query.order_by(Examen.fecha_escaneo.desc()).all()
    return jsonify([e.to_dict() for e in examenes])


@app.route('/api/examenes/<int:id>', methods=['GET'])
def get_examen(id):
    """Obtiene un examen por ID"""
    examen = Examen.query.get_or_404(id)
    return jsonify(examen.to_dict())


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


# ==================== API: NOTAS ====================

@app.route('/api/notas', methods=['GET'])
def get_notas():
    """Obtiene las notas"""
    estudiante_id = request.args.get('estudiante_id', type=int)
    curso_id = request.args.get('curso_id', type=int)
    
    query = Nota.query
    
    if estudiante_id:
        query = query.filter_by(estudiante_id=estudiante_id)
    if curso_id:
        query = query.filter_by(curso_id=curso_id)
    
    notas = query.order_by(Nota.fecha_nota.desc()).all()
    return jsonify([n.to_dict() for n in notas])


@app.route('/api/notas', methods=['POST'])
def create_nota():
    """Crea una nueva nota"""
    data = request.get_json()
    
    nota = Nota(
        estudiante_id=data['estudiante_id'],
        curso_id=data['curso_id'],
        examen_id=data.get('examen_id'),
        tipo=data.get('tipo', 'examen'),
        descripcion=data.get('descripcion', ''),
        nota=data['nota'],
        nota_maxima=data.get('nota_maxima', 10),
        porcentaje=data.get('porcentaje'),
        observaciones=data.get('observaciones', '')
    )
    
    db.session.add(nota)
    db.session.commit()
    
    return jsonify(nota.to_dict()), 201


# ==================== API: ESTADÍSTICAS ====================

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Obtiene estadísticas del sistema"""
    curso_id = request.args.get('curso_id', type=int)
    
    # Contar estudiantes
    total_estudiantes = Estudiante.query.filter_by(activo=True).count()
    
    # Contar cursos
    total_cursos = Curso.query.filter_by(activo=True).count()
    
    # Contar exámenes
    query = Examen.query
    if curso_id:
        query = query.filter_by(curso_id=curso_id)
    total_examenes = query.count()
    
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
        'total_estudiantes': total_estudiantes,
        'total_cursos': total_cursos,
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


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Error interno del servidor'}), 500


# ==================== MAIN ====================

if __name__ == '__main__':
    print("=" * 50)
    print("  GradeScanner - Sistema de Revisión de Notas")
    print("=" * 50)
    print(f"  Entorno: {config.ENV}")
    print(f"  Base de datos: {'Supabase' if config.USE_SUPABASE else 'SQLite'}")
    print(f"  Servidor iniciado en http://localhost:5000")
    print("=" * 50)
    app.run(debug=config.DEBUG, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
