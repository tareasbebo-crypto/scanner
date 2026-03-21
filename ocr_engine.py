"""
GradeScanner - Cloud OCR Engine
Motor de reconocimiento óptico de caracteres basado en API (OCR.space)
Ideal para despliegue en Render/Cloud sin dependencias locales.
"""

import os
import re
import json
import requests
from datetime import datetime

class OCREngine:
    """Motor OCR basado en la nube para máxima compatibilidad."""
    
    def __init__(self, config=None):
        self.config = config or {}
        # Clave por defecto 'helloworld' para uso de prueba (máx 500/día)
        self.api_key = self.config.get('OCR_API_KEY', 'helloworld')
        self.api_url = 'https://api.ocr.space/parse/image'
        self.language = self.config.get('languages', 'spa')

    def check_tesseract(self):
        """Mantenemos este método para compatibilidad con la UI, pero siempre devuelve OK Cloud."""
        return {
            'disponible': True,
            'version': 'Cloud API (OCR.space)',
            'idiomas': ['spa', 'eng'],
            'tiene_espanol': True,
            'ruta': 'Cloud Endpoint',
            'mensaje': 'Motor Cloud OCR conectado correctamente.'
        }

    def extract_text_with_confidence(self, image_path, whitelist=None):
        """Extrae texto enviando la imagen a la API de OCR.space."""
        if not os.path.exists(image_path):
            return {'text': '', 'confidence': 0, 'words': 0}

        try:
            with open(image_path, 'rb') as f:
                payload = {
                    'apikey': self.api_key,
                    'language': self.language,
                    'isOverlayRequired': False,
                    'detectOrientation': True,
                    'scale': True,
                    'OCREngine': 2 # Motor más moderno de OCR.space
                }
                
                # Intentamos la petición a la API
                response = requests.post(
                    self.api_url,
                    files={'file': f},
                    data=payload,
                    timeout=30 
                )
                
                if response.status_code != 200:
                    print(f"[OCR Cloud] Error HTTP: {response.status_code}")
                    return {'text': '', 'confidence': 0, 'words': 0}
                
                result = response.json()
                
                if result.get('OCRExitCode') == 1:
                    parsed_results = result.get('ParsedResults', [])
                    if parsed_results:
                        text = parsed_results[0].get('ParsedText', '')
                        words = len(text.split())
                        # OCR.space no devuelve una confianza media directa fácilmente sin overlay
                        return {'text': text.strip(), 'confidence': 95.0, 'words': words}
                
                print(f"[OCR Cloud] Error de la API: {result.get('ErrorMessage')}")
                return {'text': '', 'confidence': 0, 'words': 0}

        except Exception as e:
            print(f"[OCR Cloud] Error fatal: {str(e)}")
            return {'text': '', 'confidence': 0, 'words': 0}

    def extract_answers(self, text):
        """Extrae respuestas del texto reconocido"""
        answers = []
        patterns = [
            r'(\d+)[\.\):]\s*([A-Fa-fVv])',
            r'preg\.?\s*(\d+)[\.\):]\s*([A-Fa-fVv])',
            r'pregunta\s*(\d+)[\.\):]\s*([A-Fa-fVv])',
            r'p\.?\s*(\d+)[\.\):]\s*([A-Fa-fVv])',
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
        
        answers.sort(key=lambda x: x['pregunta'])
        # Eliminar duplicados
        seen = set()
        unique_answers = []
        for a in answers:
            if a['pregunta'] not in seen:
                unique_answers.append(a)
                seen.add(a['pregunta'])
        return unique_answers

    def extract_free_text(self, text):
        """Extrae texto por bloques de pregunta"""
        lines = text.split('\n')
        pregunta_pattern = re.compile(r'^\s*(?:pregunta\s*)?(\d+)\s*[\.\)\:]\s*(.*)$', re.IGNORECASE)
        
        bloques = {}
        pregunta_actual = None
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            match = pregunta_pattern.match(line)
            if match:
                pregunta_actual = int(match.group(1))
                bloques[pregunta_actual] = match.group(2).strip()
            elif pregunta_actual is not None:
                bloques[pregunta_actual] = bloques.get(pregunta_actual, '') + ' ' + line
        
        if not bloques:
            return {'texto_completo': text, 'respuestas_por_pregunta': {}, 'palabras': len(text.split())}
        
        return {
            'texto_completo': text,
            'respuestas_por_pregunta': {k: v.strip() for k, v in bloques.items() if v.strip()},
            'palabras': len(text.split())
        }

    def detect_student_code(self, text):
        """Detecta el código de estudiante"""
        patterns = [
            r'c[oó]digo[:\s]*([A-Z0-9]{4,15})',
            r'ID[:\s]*([A-Z0-9]{4,15})',
            r'carnet[:\s]*([A-Z0-9]{4,15})',
            r'estudiante[:\s]*([A-Z0-9]{4,15})',
            r'^([A-Z]{2,3}\d{4,8})$',
            r'(\d{6,10})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match: return match.group(1)
        return None

    def grade_answers(self, student_answers, correct_answers):
        """Califica las respuestas"""
        resultados = []
        puntos_totales = 0
        puntos_obtenidos = 0
        
        for correcta in correct_answers:
            p_num = correcta.get('pregunta')
            r_corr = correcta.get('respuesta', '').upper()
            pts = correcta.get('puntos', 1)
            
            r_stud = ''
            for ans in student_answers:
                if ans.get('pregunta') == p_num:
                    r_stud = ans.get('respuesta', '').upper()
                    break
            
            es_correcta = r_stud == r_corr
            p_obt = pts if es_correcta else 0
            
            resultados.append({
                'pregunta': p_num,
                'respuesta_estudiante': r_stud,
                'respuesta_correcta': r_corr,
                'puntos': pts,
                'puntos_obtenidos': p_obt,
                'correcta': es_correcta
            })
            puntos_totales += pts
            puntos_obtenidos += p_obt
        
        nota = (puntos_obtenidos / puntos_totales * 10) if puntos_totales > 0 else 0
        return {
            'resultados': resultados, 'nota': round(nota, 2),
            'porcentaje': round((puntos_obtenidos / puntos_totales * 100), 2) if puntos_totales > 0 else 0
        }

    def grade_free_response(self, extracted_text, preguntas):
        """Califica respuestas libres por palabras clave"""
        import difflib
        import unicodedata
        
        def normalize(t):
            if not t: return ""
            t = unicodedata.normalize('NFKD', str(t)).encode('ASCII', 'ignore').decode('utf-8')
            return t.lower()
        
        resultados = []
        puntos_totales = 0
        puntos_obtenidos = 0
        
        respuestas_por_pregunta = extracted_text.get('respuestas_por_pregunta', {})
        texto_completo = extracted_text.get('texto_completo', '')
        
        for pregunta in preguntas:
            p_num = pregunta.get('pregunta', 1)
            pts = pregunta.get('puntos', 1)
            texto_analizar = respuestas_por_pregunta.get(p_num) or respuestas_por_pregunta.get(str(p_num)) or texto_completo
            texto_norm = normalize(texto_analizar)
            
            palabras_clave = pregunta.get('palabras_clave', [])
            if isinstance(palabras_clave, str):
                palabras_clave = [p.strip() for p in palabras_clave.split(',')]
            
            match_count = 0
            found_keys = []
            for grupo in palabras_clave:
                sinonimos = [s.strip() for s in grupo.split('|')]
                for sin in sinonimos:
                    if normalize(sin) in texto_norm:
                        match_count += 1
                        found_keys.append(sinonimos[0])
                        break
            
            total_keys = len(palabras_clave)
            perc = (match_count / total_keys * 100) if total_keys > 0 else 0
            p_obt = pts if perc >= 70 else (pts * 0.6 if perc >= 40 else (pts * 0.3 if perc >= 20 else 0))
            
            resultados.append({
                'pregunta': p_num,
                'respuesta_texto': texto_analizar[:250],
                'respuesta_esperada': ', '.join([g.split('|')[0] for g in palabras_clave]),
                'palabras_clave_encontradas': found_keys,
                'coincidencias': round(perc, 2),
                'puntos': pts,
                'puntos_obtenidos': round(p_obt, 2)
            })
            puntos_totales += pts
            puntos_obtenidos += p_obt
            
        nota = (puntos_obtenidos / puntos_totales * 10) if puntos_totales > 0 else 0
        return {
            'resultados': resultados, 'nota': round(nota, 2),
            'porcentaje': round((puntos_obtenidos / puntos_totales * 100), 2) if puntos_totales > 0 else 0
        }
