"""
GradeScanner - Configuration
Manejo de configuración para diferentes entornos (local y Supabase)
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class Config:
    """Configuración base"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'gradescanner-secret-key-2024')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    OCR_API_KEY = os.environ.get('OCR_API_KEY', 'helloworld')
    
    # Determinar entorno
    ENV = os.environ.get('FLASK_ENV', 'development')
    
    # Configuración de base de datos
    USE_SUPABASE = os.environ.get('USE_SUPABASE', 'false').lower() == 'true'
    
    if USE_SUPABASE:
        # Configuración Supabase
        SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
        SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
        SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')
        
        # Usar Supabase como PostgreSQL
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', '')
        
        # Si no hay DATABASE_URL, construir desde Supabase
        if not SQLALCHEMY_DATABASE_URI and SUPABASE_URL:
            # Supabase proporciona PostgreSQL en postgres://
            SQLALCHEMY_DATABASE_URI = os.environ.get('SUPABASE_DB_URL', f'postgresql://postgres:password@db.{SUPABASE_URL.split("//")[1]}/postgres')
    else:
        # Configuración SQLite local
        BASE_DIR = os.path.abspath(os.path.dirname(__file__))
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'gradescanner.db')}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False


class DevelopmentConfig(Config):
    """Configuración de desarrollo"""
    DEBUG = True
    ENV = 'development'


class ProductionConfig(Config):
    """Configuración de producción (Render/Supabase)"""
    DEBUG = False
    ENV = 'production'
    USE_SUPABASE = True


class TestingConfig(Config):
    """Configuración de pruebas"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Configuración por defecto
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Obtiene la configuración según el entorno"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
