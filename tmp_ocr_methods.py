    def _run_ocr_and_confidence(self, img_pil):
        """Ejecuta Tesseract con una estrategia de reintentos agresiva."""
        best_text = ""
        best_words = 0
        best_cfg = self.OCR_CONFIGS[0]
        
        # Estrategia de idiomas a probar
        langs_to_try = [self.languages, 'spa', 'eng', 'spa+eng']
        # Configuraciones de PSM a probar (3 y 4 son las más útiles)
        psms = ['3', '4', '6', '11']
        
        for lang in langs_to_try:
            if best_words > 40: break # Si ya tenemos mucho texto, paramos
            for psm in psms:
                cfg = f'--oem 1 --psm {psm}'
                try:
                    t = pytesseract.image_to_string(img_pil, lang=lang, config=cfg).strip()
                    w = len(t.split())
                    if w > best_words:
                        best_words = w
                        best_text = t
                        best_cfg = cfg
                except Exception:
                    continue
        
        # Calcular confianza final
        try:
            # Usamos el idioma que más palabras nos dio para el cálculo de confianza
            data = pytesseract.image_to_data(img_pil, lang='spa' if 'spa' in self.languages else 'eng', 
                                          config=best_cfg, output_type=pytesseract.Output.DICT)
            confidences = [float(c) for i, c in enumerate(data['conf']) if str(data['text'][i]).strip() and float(c) > 0]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
        except:
            avg_conf = 0
            
        return {
            'text': best_text.strip(),
            'confidence': avg_conf,
            'words': best_words
        }

    def extract_text_with_confidence(self, image_path):
        """Extrae texto con múltiples intentos de preprocesamiento."""
        if not os.path.exists(image_path):
            return {'text': '', 'confidence': 0, 'words': 0}

        try:
            # MÉTODO 1: Imagen Original (A veces el preprocesado arruina letras finas)
            img_orig = Image.open(image_path).convert('L')
            result_orig = self._run_ocr_and_confidence(img_orig)

            # Si ya tenemos buen texto, no hace falta más
            if result_orig['words'] > 30:
                print(f"[OCR] Exito con original: {result_orig['words']} palabras")
                return result_orig

            # MÉTODO 2: Imagen Preprocesada (Recorte y binarización)
            try:
                _, _, _, _, processed = self.preprocess_image(image_path)
                img_proc = Image.fromarray(processed)
                result_proc = self._run_ocr_and_confidence(img_proc)
                
                # Devolver el mejor de los dos
                if result_proc['words'] > result_orig['words']:
                    print(f"[OCR] Exito con procesada: {result_proc['words']} palabras")
                    return result_proc
            except: pass
            
            return result_orig

        except Exception as e:
            print(f"Error fatal en OCR: {str(e)}")
            return {'text': '', 'confidence': 0, 'words': 0}
