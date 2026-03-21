"""
GradeScanner - OCR Engine
Motor de reconocimiento óptico de caracteres para exámenes
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

import platform

# ============================================================
# AUTO-DETECCIÓN DE TESSERACT (WINDOWS / LINUX)
# ============================================================
def _find_tesseract():
    """Busca tesseract.exe en rutas comunes de Windows o en el PATH de Linux."""
    if platform.system() != 'Windows':
        # En Linux/Docker (Render), simplemente lo buscamos en el PATH
        import shutil
        found = shutil.which('tesseract')
        return found

    # Candidatos para Windows
    candidatos = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Tesseract-OCR', 'tesseract.exe'),
        os.path.join(os.environ.get('APPDATA', ''), 'Tesseract-OCR', 'tesseract.exe'),
        r'C:\Tesseract-OCR\tesseract.exe'  # Ruta alternativa común
    ]
    for ruta in candidatos:
        if os.path.isfile(ruta):
            return ruta
    
    import shutil
    found = shutil.which('tesseract')
    if found:
        return found
        
    # Último intento: buscar en el PATH del sistema directamente
    try:
        from subprocess import check_output
        output = check_output(['where', 'tesseract']).decode('utf-8').strip().split('\n')[0]
        if os.path.isfile(output):
            return output
    except:
        pass
        
    return None

TESSERACT_PATH = _find_tesseract()
if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    print(f"[OCR] Tesseract configurado en: {TESSERACT_PATH}")
else:
    print("[OCR] ADVERTENCIA: Tesseract no encontrado. El OCR fallará.")

TESSERACT_DISPONIBLE = TESSERACT_PATH is not None

class OCREngine:
    """Motor OCR para reconocimiento de texto en imágenes de exámenes"""
    
    # ---- Configuraciones de Tesseract a probar (de mayor a menor agresividad) ----
    OCR_CONFIGS = [
        r'--oem 1 --psm 6',   # LSTM, bloque uniforme (bueno para exámenes estructurados)
        r'--oem 1 --psm 4',   # LSTM, bloque de texto multi-línea (mejor para redacción libre)
        r'--oem 1 --psm 11',  # Texto disperso (CRUCIAL para hojas de burbujas/OMR)
        r'--oem 1 --psm 3',   # LSTM, detección automática de página
        r'--oem 3 --psm 6',   # Motores combinados
    ]

    def __init__(self, config=None):
        self.config = config or {}
        self.custom_config = r'--oem 1 --psm 4'
        self.languages = self.config.get('languages', 'spa+eng')
        self._tesseract_ok = TESSERACT_DISPONIBLE

    def check_tesseract(self):
        """Verifica disponibilidad de Tesseract y retorna estado."""
        if not self._tesseract_ok:
            return {
                'disponible': False,
                'mensaje': 'Tesseract OCR no está instalado. Descárgalo de https://github.com/UB-Mannheim/tesseract/releases e instálalo marcando el idioma "Spanish".',
                'ruta': None
            }
        try:
            version = pytesseract.get_tesseract_version()
            langs = pytesseract.get_languages()
            tiene_spa = 'spa' in langs
            return {
                'disponible': True,
                'version': str(version),
                'idiomas': langs,
                'tiene_espanol': tiene_spa,
                'ruta': TESSERACT_PATH,
                'mensaje': f'Tesseract {version} OK. Español: {"sí" if tiene_spa else "NO - instala spa.traineddata"}'
            }
        except Exception as e:
            return {
                'disponible': False,
                'mensaje': str(e),
                'ruta': TESSERACT_PATH
            }

    def _order_points(self, pts):
        """Ordena 4 puntos: top-left, top-right, bottom-right, bottom-left."""
        rect = np.zeros((4, 2), dtype='float32')
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    def _four_point_transform(self, image, pts):
        """Aplica perspectiva (bird-eye view) recortando al rectángulo del papel."""
        rect = self._order_points(pts)
        (tl, tr, br, bl) = rect
        widthA = np.linalg.norm(br - bl)
        widthB = np.linalg.norm(tr - tl)
        maxW = max(int(widthA), int(widthB))
        heightA = np.linalg.norm(tr - br)
        heightB = np.linalg.norm(tl - bl)
        maxH = max(int(heightA), int(heightB))
        dst = np.array([[0,0],[maxW-1,0],[maxW-1,maxH-1],[0,maxH-1]], dtype='float32')
        M = cv2.getPerspectiveTransform(rect, dst)
        return cv2.warpPerspective(image, M, (maxW, maxH))

    def _detect_and_crop_paper(self, img):
        """Detecta el contorno del papel en el fondo y lo recorta/endereza."""
        orig_h, orig_w = img.shape[:2]
        # Redimensionar para detección rápida
        scale = 800 / max(orig_h, orig_w)
        small = cv2.resize(img, None, fx=scale, fy=scale)

        gray_s = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        blur_s = cv2.GaussianBlur(gray_s, (5, 5), 0)
        edged = cv2.Canny(blur_s, 50, 200)
        edged = cv2.dilate(edged, np.ones((3,3), np.uint8), iterations=2)

        cnts, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:6]

        paper_pts = None
        for c in cnts:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4 and cv2.contourArea(approx) > (orig_h * orig_w * scale**2 * 0.15):
                paper_pts = approx.reshape(4, 2) / scale
                break

        if paper_pts is not None:
            return self._four_point_transform(img, paper_pts)
        return img  # Si no detecta papel, devuelve original

    def _deskew(self, gray):
        """Detecta y corrige la inclinación del texto (hasta ±45°)."""
        coords = np.column_stack(np.where(gray < 128))
        if len(coords) < 10:
            return gray
        angle = cv2.minAreaRect(coords.astype(np.float32))[-1]
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = angle - 90
        if abs(angle) < 0.3:
            return gray  # Prácticamente derecho, no tocar
        (h, w) = gray.shape
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)

    def preprocess_image(self, image_path):
        """Pipeline completo de preprocesamiento para OCR robusto.
        
        Pasos:
        1. Detección y recorte del papel (no importa si está descentrado).
        2. Escala ×2 para resolución alta.
        3. Normalización de iluminación con CLAHE.
        4. Filtro bilateral (quita ruido, conserva bordes de letra).
        5. Corrección automática de inclinación (deskew).
        6. Binarización adaptativa.
        7. Erosión leve para afinar trazos.
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"No se pudo cargar la imagen: {image_path}")

        # 1. Recortar el papel del fondo (funciona aunque esté inclinado/descentrado)
        img = self._detect_and_crop_paper(img)

        # 2. Escalar ×2 para mayor detalle
        img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        # 3. Escala de grises
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 4. CLAHE (normaliza iluminación: sombras de mano, flash, etc.)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # 5. Filtro bilateral (suaviza ruido sin destruir bordes de letras)
        blur = cv2.bilateralFilter(gray, 9, 75, 75)

        # 6. Deskew: corrige texto inclinado hasta ±45°
        blur = self._deskew(blur)

        # 7. Binarización adaptativa
        thresh = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 15
        )

        # 8. Erosión leve para afinar trazos de bolígrafo débil
        kernel = np.ones((2, 2), np.uint8)
        processed = cv2.erode(thresh, kernel, iterations=1)

        return img, gray, blur, thresh, processed

    def _run_ocr_and_confidence(self, img_pil, whitelist=None):
        """Ejecuta Tesseract con una estrategia de reintentos agresiva."""
        if not TESSERACT_DISPONIBLE:
            return {'text': '', 'confidence': 0, 'words': 0}
            
        best_text = ""
        best_words = 0
        best_cfg = self.OCR_CONFIGS[0]
        
        # Configuración extra opcional (whitelist)
        extra_cfg = ""
        if whitelist:
            extra_cfg = f"-c tessedit_char_whitelist={whitelist}"
            
        # Estrategia de idiomas y PSMs a probar
        langs_to_try = [self.languages, 'spa', 'spa+eng', 'eng']
        psms = ['6', '11', '4', '3']
        
        for lang in langs_to_try:
            if best_words > 50: break
            for psm in psms:
                cfg = f'--oem 1 --psm {psm} {extra_cfg}'.strip()
                try:
                    t = pytesseract.image_to_string(img_pil, lang=lang, config=cfg).strip()
                    w = len(t.split())
                    if w > best_words:
                        best_words = w
                        best_text = t
                        best_cfg = cfg
                        if best_words > 30: break
                except Exception as e:
                    print(f"[OCR] Error con PSM {psm}: {str(e)}")
                    continue
        
        # Calcular confianza final
        try:
            data = pytesseract.image_to_data(img_pil, lang='spa' if 'spa' in self.languages else 'eng', 
                                          config=best_cfg, output_type=pytesseract.Output.DICT)
            confidences = [float(c) for i, c in enumerate(data['conf']) if str(data['text'][i]).strip() and float(c) > 0]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
        except:
            avg_conf = 0
            
        return {'text': best_text.strip(), 'confidence': avg_conf, 'words': best_words}

    def extract_text_with_confidence(self, image_path, whitelist=None):
        """Extrae texto con múltiples intentos de preprocesamiento."""
        if not os.path.exists(image_path):
            return {'text': '', 'confidence': 0, 'words': 0}

        if not TESSERACT_DISPONIBLE:
            print("[OCR] Fallo: Tesseract no disponible.")
            return {'text': '', 'confidence': 0, 'words': 0}

        try:
            # MÉTODO 1: Imagen Original
            img_orig = Image.open(image_path).convert('L')
            result_orig = self._run_ocr_and_confidence(img_orig, whitelist)
            print(f"[OCR] Intento 1 (Original): {result_orig['words']} palabras")

            # Si ya tenemos muy buen texto, no hace falta más
            if result_orig['words'] > 40:
                return result_orig

            # MÉTODO 2: Imagen Procesada (Binarizada con Erosión)
            try:
                raw_img = cv2.imread(image_path)
                # Recorte de papel
                paper = self._detect_and_crop_paper(raw_img)
                # Escalar x2
                paper_scaled = cv2.resize(paper, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                gray = cv2.cvtColor(paper_scaled, cv2.COLOR_BGR2GRAY)
                # Binarización
                thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
                # Erosión (el método original)
                kernel = np.ones((2, 2), np.uint8)
                processed = cv2.erode(thresh, kernel, iterations=1)
                
                img_proc = Image.fromarray(processed)
                result_proc = self._run_ocr_and_confidence(img_proc, whitelist)
                print(f"[OCR] Intento 2 (Binarizado + Erosión): {result_proc['words']} palabras")
                
                if result_proc['words'] > result_orig['words']:
                    result_orig = result_proc
            except Exception as e:
                print(f"[OCR] Error en intento 2: {str(e)}")

            if result_orig['words'] > 30:
                return result_orig

            # MÉTODO 3: Binarizada SIN Erosión (mejor para fuentes delgadas)
            try:
                # Usamos thresh del paso anterior (si falló por la erosión)
                img_no_erode = Image.fromarray(thresh)
                result_no_erode = self._run_ocr_and_confidence(img_no_erode, whitelist)
                print(f"[OCR] Intento 3 (Sin Erosión): {result_no_erode['words']} palabras")
                
                if result_no_erode['words'] > result_orig['words']:
                    return result_no_erode
            except: pass
            
            return result_orig

        except Exception as e:
            print(f"Error fatal en OCR: {str(e)}")
            return {'text': '', 'confidence': 0, 'words': 0}

    
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
