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
    
    # Configurar URI según el entorno
    if config.USE_SUPABASE:
        # Usar PostgreSQL de Supabase
        app.config['SQLALCHEMY_DATABASE_URI'] = config.SQLALCHEMY_DATABASE_URI
        print(f"✓ Conectando a Supabase/PostgreSQL")
    else:
        # Usar SQLite local
        db_path = get_database_path()
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
        print(f"✓ Usando SQLite local: {db_path}")
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ECHO'] = config.DEBUG
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        print("✓ Base de datos inicializada correctamente")
        
    return db
