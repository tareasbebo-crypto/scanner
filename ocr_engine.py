"""
GradeScanner - OCR Engine
Motor de reconocimiento óptico de caracteres para escaneo de exámenes
Soporta opción múltiple y opción libre (respuesta abierta)
"""

import os
import re
import json
import cv2
import numpy as np
from PIL import Image
import pytesseract
from datetime import datetime

# Configuración de Tesseract (ajusta la ruta si es necesario en Windows)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class OCREngine:
    """Motor OCR para reconocimiento de texto en imágenes de exámenes"""
    
    def __init__(self, config=None):
        self.config = config or {}
        # Configuración de Tesseract
        # --oem 1 usa Neural Nets LSTM, --psm 4 asume una sola columna de texto de tamaños variables
        self.custom_config = r'--oem 1 --psm 4'
        self.languages = self.config.get('languages', 'spa+eng')
    
    def preprocess_image(self, image_path):
        """Preprocesa la imagen para mejorar la lectura de letra a mano/fea"""
        # Leer imagen
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"No se pudo cargar la imagen: {image_path}")
        
        # 1. Redimensionar para mayor resolución (ayuda mucho a Tesseract con la letra fea)
        img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        # 2. Convertir a escala de grises
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 3. Eliminar sombras e iluminación desigual usando un filtro de top-hat o CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
        
        # 4. Reducción ligera de ruido conservando bordes (Bilateral Filter)
        blur = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # 5. Binarización adaptativa inteligente (ideal para tinta vs papel irregular)
        thresh = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 31, 15
        )
        
        # Opcional: Filtro de máscara para engrosar un poco los bordes de letras de bolígrafo débiles
        kernel = np.ones((2, 2), np.uint8)
        processed = cv2.erode(thresh, kernel, iterations=1)
        
        return img, gray, blur, thresh, processed
    
    def extract_text(self, image_path, preprocess=True):
        """Extrae texto de una imagen"""
        try:
            if preprocess:
                # Usar imagen preprocesada con filtro para letra fea
                _, _, _, _, processed = self.preprocess_image(image_path)
                
                # Como binarizamos modo normal (texto negro fondo blanco),
                # no necesitamos revertir colores antes de enviar a Tesseract.
                img_pil = Image.fromarray(processed)
            else:
                img_pil = Image.open(image_path)
            
            # Extraer texto con Tesseract usando LSTM y PSM optimizado
            text = pytesseract.image_to_string(
                img_pil, 
                lang=self.languages,
                config=self.custom_config
            )
            
            return text.strip()
        except Exception as e:
            print(f"Error en OCR: {str(e)}")
            return ""
    
    def extract_text_with_confidence(self, image_path):
        """Extrae texto con información de confianza"""
        try:
            # Usar la imagen preprocesada optimizada en lugar de la cruda
            _, _, _, _, processed = self.preprocess_image(image_path)
            img_pil = Image.fromarray(processed)
            
            # Obtener datos OCR con confianza
            data = pytesseract.image_to_data(
                img_pil, 
                lang=self.languages,
                config=self.custom_config,
                output_type=pytesseract.Output.DICT
            )
            
            text_parts = []
            confidences = []
            
            for i, text in enumerate(data['text']):
                if text.strip():
                    text_parts.append(text)
                    conf = float(data['conf'][i])
                    if conf > 0:
                        confidences.append(conf)
            
            full_text = ' '.join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            return {
                'text': full_text,
                'confidence': avg_confidence,
                'words': len(text_parts)
            }
        except Exception as e:
            print(f"Error en OCR con confianza: {str(e)}")
            return {
                'text': '',
                'confidence': 0,
                'words': 0
            }
    
    def extract_answers(self, text, answer_pattern=None):
        """Extrae respuestas de opción múltiple del texto reconocido"""
        answers = []
        
        # Patrones comunes para respuestas (soporta A-F y Verdadero/Falso V/F)
        patterns = [
            r'(\d+)[\.\):]\s*([A-Fa-fVv])',  # 1. A, 1) A, 1: A, 1. V, 1. F
            r'preg\.?\s*(\d+)[\.\):]\s*([A-Fa-fVv])',  # preg. 1 A
            r'pregunta\s*(\d+)[\.\):]\s*([A-Fa-fVv])',  # pregunta 1 A
            r'p\.?\s*(\d+)[\.\):]\s*([A-Fa-fVv])',  # p. 1 A
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                pregunta_num = int(match.group(1))
                respuesta = match.group(2).upper()
                answers.append({
                    'pregunta': pregunta_num,
                    'respuesta': respuesta,
                    'match': match.group(0)
                })
        
        # Ordenar por número de pregunta
        answers.sort(key=lambda x: x['pregunta'])
        return answers
    
    def extract_free_text(self, text):
        """Extrae texto para preguntas de respuesta libre.
        
        Intenta segmentar el texto por número de pregunta para 
        tratar cada respuesta por separado (admite escritura cursiva/manuscrita).
        """
        lines = text.split('\n')
        
        # Intentar separar respuestas por número de pregunta
        # Patrón: "1.", "1)", "Pregunta 1:", "P1:", etc.
        pregunta_pattern = re.compile(
            r'^\s*(?:pregunta\s*)?(\d+)\s*[\.\)\:]\s*(.*)$', re.IGNORECASE
        )
        
        bloques = {}  # {num_pregunta: texto_respuesta}
        pregunta_actual = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            match = pregunta_pattern.match(line)
            if match:
                pregunta_actual = int(match.group(1))
                resto = match.group(2).strip()
                bloques[pregunta_actual] = resto
            elif pregunta_actual is not None:
                # Continuar acumulando texto de la misma pregunta
                bloques[pregunta_actual] = bloques.get(pregunta_actual, '') + ' ' + line
        
        # Si no se pudo segmentar, devolver texto completo como una sola respuesta
        if not bloques:
            cleaned = [l.strip() for l in lines if l.strip() and not re.match(r'^[\d\.\)\(:]+$', l.strip())]
            return {
                'texto_completo': text,
                'lineas_limpias': cleaned,
                'palabras': len(text.split()),
                'respuestas_por_pregunta': {}
            }
        
        # Limpiar textos de cada bloque
        respuestas_limpias = {k: v.strip() for k, v in bloques.items() if v.strip()}
        
        return {
            'texto_completo': text,
            'lineas_limpias': [f"{k}. {v}" for k, v in respuestas_limpias.items()],
            'palabras': len(text.split()),
            'respuestas_por_pregunta': respuestas_limpias  # {1: "respuesta...", 2: "respuesta..."}
        }
    
    def detect_student_code(self, text):
        """Detecta el código de estudiante en el texto"""
        # Patrones comunes para códigos de estudiante
        patterns = [
            r'c[oó]digo[:\s]*([A-Z0-9]{4,15})',
            r'ID[:\s]*([A-Z0-9]{4,15})',
            r'carnet[:\s]*([A-Z0-9]{4,15})',
            r'estudiante[:\s]*([A-Z0-9]{4,15})',
            r'^([A-Z]{2,3}\d{4,8})$',  # Al inicio: ABC12345
            r'(\d{6,10})',  # Solo números
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1)
        
        return None
    
    def extract_questions_answers(self, text):
        """Extrae preguntas y respuestas del texto completo"""
        results = {
            'texto_completo': text,
            'codigo_estudiante': self.detect_student_code(text),
            'respuestas': self.extract_answers(text),
            'palabras': len(text.split()),
            'lineas': len(text.split('\n'))
        }
        
        return results
    
    def grade_answers(self, student_answers, correct_answers):
        """Califica las respuestas de opción múltiple"""
        resultados = []
        puntos_totales = 0
        puntos_obtenidos = 0
        
        for correcta in correct_answers:
            pregunta_num = correcta.get('pregunta')
            respuesta_correcta = correcta.get('respuesta', '').upper()
            puntos = correcta.get('puntos', 1)
            
            # Buscar respuesta del estudiante
            respuesta_estudiante = ''
            for respuesta in student_answers:
                if respuesta.get('pregunta') == pregunta_num:
                    respuesta_estudiante = respuesta.get('respuesta', '').upper()
                    break
            
            # Calcular puntos
            es_correcta = respuesta_estudiante == respuesta_correcta
            puntos_q = puntos if es_correcta else 0
            
            resultados.append({
                'pregunta': pregunta_num,
                'respuesta_estudiante': respuesta_estudiante,
                'respuesta_correcta': respuesta_correcta,
                'puntos': puntos,
                'puntos_obtenidos': puntos_q,
                'correcta': es_correcta
            })
            
            puntos_totales += puntos
            puntos_obtenidos += puntos_q
        
        # Calcular nota sobre 10
        nota = (puntos_obtenidos / puntos_totales * 10) if puntos_totales > 0 else 0
        
        return {
            'resultados': resultados,
            'puntos_totales': puntos_totales,
            'puntos_obtenidos': puntos_obtenidos,
            'nota': round(nota, 2),
            'porcentaje': round((puntos_obtenidos / puntos_totales * 100), 2) if puntos_totales > 0 else 0
        }
    
    def grade_free_response(self, extracted_text, preguntas):
        """Califica respuestas de opción libre comparando palabras clave.
        
        Evalúa cada pregunta en su propio bloque (si el alumno numeró las respuestas),
        o en el texto completo como fallback. Tolera errores ortográficos y sinónimos.
        """
        import difflib
        import unicodedata
        
        def normalize(text):
            if not text: return ""
            text = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8')
            return text.lower()
        
        def buscar_palabra(sinonimos_grupo, texto_norm):
            """Busca un grupo de sinónimos en el texto con tolerancia."""
            for sinonimo in sinonimos_grupo:
                sinonimo_norm = normalize(sinonimo)
                if not sinonimo_norm:
                    continue
                # 1. Búsqueda exacta
                if sinonimo_norm in texto_norm:
                    return True
                # 2. Búsqueda difusa por palabras
                words = texto_norm.split()
                s_words = sinonimo_norm.split()
                n = len(s_words)
                for i in range(len(words) - n + 1):
                    fragmento = " ".join(words[i:i+n])
                    if difflib.SequenceMatcher(None, sinonimo_norm, fragmento).ratio() >= 0.80:
                        return True
            return False
        
        resultados = []
        puntos_totales = 0
        puntos_obtenidos = 0
        
        # Obtener respuestas segmentadas por pregunta (si existen)
        respuestas_por_pregunta = extracted_text.get('respuestas_por_pregunta', {})
        texto_completo = extracted_text.get('texto_completo', '')
        
        for pregunta in preguntas:
            pregunta_num = pregunta.get('pregunta', 1)
            puntos = pregunta.get('puntos', 1)
            
            # Determinar el texto a analizar: bloque específico o texto completo
            if pregunta_num in respuestas_por_pregunta:
                texto_analizar = respuestas_por_pregunta[pregunta_num]
                fuente = 'bloque'
            elif str(pregunta_num) in respuestas_por_pregunta:
                texto_analizar = respuestas_por_pregunta[str(pregunta_num)]
                fuente = 'bloque'
            else:
                # Fallback: cada pregunta analizada en el texto completo
                texto_analizar = texto_completo
                fuente = 'texto_completo'
            
            texto_norm = normalize(texto_analizar)
            
            # Obtener palabras clave
            palabras_clave = pregunta.get('palabras_clave', [])
            if isinstance(palabras_clave, str):
                palabras_clave = [p.strip() for p in palabras_clave.split(',')]
            
            # Contar coincidencias
            coincidencias_encontradas = 0
            encontradas = []
            
            for grupo_palabra in palabras_clave:
                sinonimos = [s.strip() for s in grupo_palabra.split('|')]
                if buscar_palabra(sinonimos, texto_norm):
                    coincidencias_encontradas += 1
                    encontradas.append(sinonimos[0])
            
            total_palabras = len(palabras_clave)
            porcentaje = (coincidencias_encontradas / total_palabras * 100) if total_palabras > 0 else 0
            
            # Calificación proporcional
            if porcentaje >= 70:
                puntos_obtenidos_q = puntos
            elif porcentaje >= 40:
                puntos_obtenidos_q = puntos * 0.6
            elif porcentaje >= 20:
                puntos_obtenidos_q = puntos * 0.3
            else:
                puntos_obtenidos_q = 0
            
            texto_preview = texto_analizar[:250] + '...' if len(texto_analizar) > 250 else texto_analizar
            
            resultados.append({
                'pregunta': pregunta_num,
                'respuesta_texto': texto_preview,
                'respuesta_esperada': ', '.join([g.split('|')[0].strip() for g in palabras_clave]),
                'palabras_clave_encontradas': encontradas,
                'coincidencias': round(porcentaje, 2),
                'fuente_analisis': fuente,
                'puntos': puntos,
                'puntos_obtenidos': round(puntos_obtenidos_q, 2)
            })
            
            puntos_totales += puntos
            puntos_obtenidos += puntos_obtenidos_q
        
        nota = (puntos_obtenidos / puntos_totales * 10) if puntos_totales > 0 else 0
        
        return {
            'resultados': resultados,
            'puntos_totales': puntos_totales,
            'puntos_obtenidos': round(puntos_obtenidos, 2),
            'nota': round(nota, 2),
            'porcentaje': round((puntos_obtenidos / puntos_totales * 100), 2) if puntos_totales > 0 else 0
        }


def process_exam_image(image_path, correct_answers=None, tipo_examen='multiple_choice', config=None):
    """Procesa una imagen de examen y retorna los resultados"""
    engine = OCREngine(config)
    
    # Extraer texto con confianza
    ocr_result = engine.extract_text_with_confidence(image_path)
    
    # Extraer preguntas y respuestas según el tipo
    if tipo_examen == 'multiple_choice':
        extracted = engine.extract_answers(ocr_result['text'])
    else:
        extracted = engine.extract_free_text(ocr_result['text'])
    
    # Detectar código de estudiante
    student_code = engine.detect_student_code(ocr_result['text'])
    
    result = {
        'image_path': image_path,
        'text': ocr_result['text'],
        'confidence': ocr_result['confidence'],
        'words': ocr_result['words'],
        'extracted_answers': extracted,
        'student_code': student_code,
        'timestamp': datetime.now().isoformat()
    }
    
    # Si hay respuestas correctas, calificar
    if correct_answers:
        if tipo_examen == 'multiple_choice':
            grade_result = engine.grade_answers(extracted, correct_answers)
        else:
            grade_result = engine.grade_free_response(extracted, correct_answers)
        result['grade'] = grade_result
    
    return result


# Ejemplo de uso
if __name__ == '__main__':
    # Prueba básica
    print("GradeScanner OCR Engine inicializado")
    print("Funciones disponibles:")
    print("- extract_text(): Extrae texto de una imagen")
    print("- extract_text_with_confidence(): Extrae texto con nivel de confianza")
    print("- extract_answers(): Extrae respuestas type A/B/C/D (opción múltiple)")
    print("- extract_free_text(): Extrae texto para respuesta libre")
    print("- grade_answers(): Califica respuestas múltiples")
    print("- grade_free_response(): Califica respuestas por palabras clave")
