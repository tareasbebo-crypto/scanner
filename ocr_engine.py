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
            return {'text': '', 'confidence': 0, 'words': 0, 'error': 'File not found'}

        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
                
            # Check file size (OCR.space has 2MB limit for free tier)
            if len(image_data) > 2 * 1024 * 1024:
                return {'text': '', 'confidence': 0, 'words': 0, 'error': 'Image too large (max 2MB)'}
            
            payload = {
                'apikey': self.api_key,
                'language': self.language,
                'isOverlayRequired': False,
                'detectOrientation': True,
                'scale': True,
                'OCREngine': 2
            }
            
            response = requests.post(
                self.api_url,
                files={'file': ('image.jpg', image_data, 'image/jpeg')},
                data=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"[OCR] HTTP Error: {response.status_code} - {response.text[:200]}")
                return {'text': '', 'confidence': 0, 'words': 0, 'error': f'HTTP {response.status_code}'}
            
            result = response.json()
            
            # Debug: Log the API response
            print(f"[OCR] ExitCode: {result.get('OCRExitCode')}")
            if result.get('ErrorMessage'):
                print(f"[OCR] ErrorMessage: {result.get('ErrorMessage')}")
            
            if result.get('OCRExitCode') == 1:
                parsed_results = result.get('ParsedResults', [])
                if parsed_results:
                    text = parsed_results[0].get('ParsedText', '')
                    if text and text.strip():
                        words = len(text.split())
                        # Get confidence from result if available
                        confidence = 90.0  # Default high confidence
                        if 'TextConfidence' in parsed_results[0]:
                            conf_data = parsed_results[0].get('TextConfidence', {})
                            confidence = conf_data.get('Mean', 90.0)
                        
                        print(f"[OCR] Success: {words} words extracted")
                        return {'text': text.strip(), 'confidence': confidence, 'words': words}
                    else:
                        return {'text': '', 'confidence': 0, 'words': 0, 'error': 'No text detected in image'}
                
                return {'text': '', 'confidence': 0, 'words': 0, 'error': 'No parsed results'}
            
            # Handle API errors
            error_msg = result.get('ErrorMessage', 'Unknown error')
            if isinstance(error_msg, list):
                error_msg = error_msg[0] if error_msg else 'Unknown error'
            
            print(f"[OCR] API Error: {error_msg}")
            return {'text': '', 'confidence': 0, 'words': 0, 'error': str(error_msg)}

        except requests.exceptions.Timeout:
            print("[OCR] Timeout error")
            return {'text': '', 'confidence': 0, 'words': 0, 'error': 'API timeout'}
        except requests.exceptions.ConnectionError as e:
            print(f"[OCR] Connection error: {e}")
            return {'text': '', 'confidence': 0, 'words': 0, 'error': 'Connection failed'}
        except Exception as e:
            print(f"[OCR] Error: {str(e)}")
            return {'text': '', 'confidence': 0, 'words': 0, 'error': str(e)}

    def extract_answers(self, text):
        """Extrae respuestas del texto reconocido"""
        # Log del texto para depuración remota
        print(f"\n--- DEBUG OCR TEXT START ---\n{text}\n--- DEBUG OCR TEXT END ---\n")
        
        answers = []
        # Patrones robustos para OCR en condiciones difíciles (skew, perspectiva)
        # 1. Soporta números con varios separadores (., :, ), -, ,, etc)
        # 2. Soporta símbolos de marcado: ●, *, X, V, •, ■, ☒
        # 4. Soporta letras de opción: A-F
        patterns = [
            # Formato estándar con separador flexible: 1. A o 1: B
            r'(\d+)\s*[\.\,;:\)\-\/_]?\s*([A-F]|[VvFf]|[●\*•■☒])',
            
            # Formato con prefijo: Pregunta 1: A
            r'(?:preg|pregunta|p)\.?\s*(\d+)\s*[\.\,;:\)\-\/_]?\s*([A-F]|[VvFf]|[●\*•■☒])',
            
            # Formato de lista simple (número seguido de espacio y letra/símbolo): 1 A
            r'^\s*(\d+)\s+([A-F]|[VvFf]|[●\*•■☒])',
            
            # Formato de marcado entre paréntesis: 1 (X)
            r'(\d+)\s*[\.\,;:\)\-\/_]?\s*\(([A-F]|[VvFf]|X|x|●|\*|•)\)',
        ]
        
        for pattern in patterns:
            # MULTILINE para ^ al inicio de línea, IGNORECASE para letras
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                try:
                    pregunta_num = int(match.group(1))
                    val = match.group(2).upper()
                    
                    # Normalización de símbolos a caracteres estándar si es posible
                    if val in ['●', '*', '•', '■', '☒']:
                        respuesta = val # Mantenemos el símbolo para revisión manual o lógica posterior
                    else:
                        respuesta = val
                        
                    answers.append({
                        'pregunta': pregunta_num,
                        'respuesta': respuesta,
                        'match': match.group(0).strip()
                    })
                    print(f"[OCR] Match encontrado: {match.group(0).strip()} -> P{pregunta_num}:{respuesta}")
                except Exception as e:
                    print(f"[OCR] Error procesando match: {e}")
        
        # Ordenar por número de pregunta
        answers.sort(key=lambda x: x['pregunta'])
        
        # Eliminar duplicados prefiriendo el primer match encontrado (el más cercano al número)
        seen = set()
        unique_answers = []
        for a in answers:
            if a['pregunta'] not in seen:
                unique_answers.append(a)
                seen.add(a['pregunta'])
        
        print(f"[OCR] Total respuestas únicas detectadas: {len(unique_answers)}")
        return unique_answers

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
