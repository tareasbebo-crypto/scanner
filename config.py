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
    
    # Obtener DATABASE_URL (Render proporciona esta variable)
    # Nota: Render a veces envía 'postgres://' pero SQLAlchemy requiere 'postgresql://'
    database_url = os.environ.get('DATABASE_URL', '')
    
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    if USE_SUPABASE and database_url:
        SQLALCHEMY_DATABASE_URI = database_url
        print(f"✓ Conectando a PostgreSQL/Supabase (detectado vía DATABASE_URL)")
    elif USE_SUPABASE:
        # Configuración manual de Supabase si no hay DATABASE_URL
        SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
        SUPABASE_DB_URL = os.environ.get('SUPABASE_DB_URL', '')
        
        if SUPABASE_DB_URL:
            if SUPABASE_DB_URL.startswith("postgres://"):
                SUPABASE_DB_URL = SUPABASE_DB_URL.replace("postgres://", "postgresql://", 1)
            SQLALCHEMY_DATABASE_URI = SUPABASE_DB_URL
            print(f"✓ Conectando a PostgreSQL/Supabase (detectado vía SUPABASE_DB_URL)")
        elif SUPABASE_URL:
            try:
                project_ref = SUPABASE_URL.split('//')[1].split('.')[0]
                # Fallback, el usuario debería proveer la URL completa
                SQLALCHEMY_DATABASE_URI = f'postgresql://postgres:password@db.{project_ref}.supabase.co:5432/postgres'
                print(f"✓ Reconstruyendo URL de Supabase desde SUPABASE_URL")
            except:
                SQLALCHEMY_DATABASE_URI = ''
        else:
            SQLALCHEMY_DATABASE_URI = ''
        print(f"✓ Configuración Supabase manual result: {bool(SQLALCHEMY_DATABASE_URI)}")
    else:
        # Configuración SQLite local
        BASE_DIR = os.path.abspath(os.path.dirname(__file__))
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'gradescanner.db')}"
        print(f"✓ Usando SQLite local")
    
    # Debug: Mostrar que tenemos configurado (sin mostrar contraseña)
    if SQLALCHEMY_DATABASE_URI:
        print(f"[DEBUG] DB Configurada: {SQLALCHEMY_DATABASE_URI.split(':')[0]}...")
    else:
        print("[DEBUG] DB NO CONFIGURADA")
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = True  # Enable for debugging


class DevelopmentConfig(Config):
    """Configuración de desarrollo"""
    DEBUG = True
    ENV = 'development'
    USE_SUPABASE = False  # SQLite local


class ProductionConfig(Config):
    """Configuración de producción (Render/Supabase)"""
    DEBUG = False
    ENV = 'production'
    SQLALCHEMY_ECHO = False


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
