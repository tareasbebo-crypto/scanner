"""
GradeScanner - Database Configuration
Configuración de la base de datos SQLite o PostgreSQL (Supabase)
"""

import os
from flask_sqlalchemy import SQLAlchemy

# Instancia global de SQLAlchemy
db = SQLAlchemy()


def get_database_path():
    """Obtiene la ruta de la base de datos SQLite (solo para desarrollo local)"""
    base_dir = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_dir, 'gradescanner.db')


def init_app(app):
    """Inicializa la base de datos con la aplicación Flask"""
    from config import get_config
    
    config = get_config()
    
    # Verificar que tenemos una URL de base de datos válida
    db_uri = config.SQLALCHEMY_DATABASE_URI
    
    if not db_uri or db_uri == 'sqlite:///':
        # Error: No hay base de datos configurada
        print(f"ERROR: No se ha configurado la base de datos! (URI detectada: '{db_uri}')")
        print(f"Entorno: {os.environ.get('FLASK_ENV', 'N/A')}")
        print(f"DATABASE_URL presente en ENV: {bool(os.environ.get('DATABASE_URL'))}")
        print("Para SQLite local: USE_SUPABASE=false")
        print("Para Supabase: USE_SUPABASE=true y DATABASE_URL=[tu-url]")
        raise ValueError(f"DATABASE_URL no configurada correctamente (URI: '{db_uri}')")
    
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ECHO'] = config.DEBUG
    
    db.init_app(app)
    
    with app.app_context():
        # create_all() NO borra tablas existentes, solo las crea si no existen
        db.create_all()
        
        # Verificar que las tablas existen
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if tables:
            print(f"✓ Base de datos conectada. Tablas: {', '.join(tables)}")
        else:
            print("⚠ Tablas creadas (base de datos vacía)")
        
        print(f"✓ URI de base de datos: {db_uri.split('@')[0]}@***")  # Hide password
        
    return db
