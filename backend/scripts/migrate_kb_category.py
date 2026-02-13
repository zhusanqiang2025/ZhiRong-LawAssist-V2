import sys
import os

# Add backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from app.core.config import settings
from dotenv import load_dotenv
import logging

load_dotenv()

# 使用新的日志配置
from app.core.logger import setup_logging
setup_logging()
logger = logging.getLogger("legal_assistant")

def migrate():
    db_url = settings.DATABASE_URL
    if not db_url:
        logger.error("DATABASE_URL not found in settings")
        return
    
    # Fix for local execution if db host is 'db' (docker network)
    if "@db:" in db_url:
        logger.info("Replacing 'db' host with 'localhost' for migration script...")
        db_url = db_url.replace("@db:", "@localhost:")
        
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        try:
            # Check if category_id exists
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='knowledge_documents' AND column_name='category_id'"))
            if result.fetchone():
                logger.info("Column 'category_id' already exists.")
            else:
                logger.info("Adding 'category_id' column...")
                conn.execute(text("ALTER TABLE knowledge_documents ADD COLUMN category_id INTEGER REFERENCES categories(id)"))
                conn.execute(text("CREATE INDEX ix_knowledge_documents_category_id ON knowledge_documents (category_id)"))
                logger.info("Column 'category_id' and index added.")

            # Check if category_name_cache exists
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='knowledge_documents' AND column_name='category_name_cache'"))
            if result.fetchone():
                logger.info("Column 'category_name_cache' already exists.")
            else:
                logger.info("Adding 'category_name_cache' column...")
                conn.execute(text("ALTER TABLE knowledge_documents ADD COLUMN category_name_cache VARCHAR(100)"))
                logger.info("Column 'category_name_cache' added.")
                
            # Migrate data: copy old category to cache
            # Check if old category column exists
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='knowledge_documents' AND column_name='category'"))
            if result.fetchone():
                logger.info("Migrating data from 'category' to 'category_name_cache'...")
                conn.execute(text("UPDATE knowledge_documents SET category_name_cache = category WHERE category IS NOT NULL"))
                # Optional: Drop old column via raw SQL if needed, but usually we keep it or rename it.
                # conn.execute(text("ALTER TABLE knowledge_documents DROP COLUMN category"))
                logger.info("Data migration complete.")
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            
if __name__ == "__main__":
    migrate()
