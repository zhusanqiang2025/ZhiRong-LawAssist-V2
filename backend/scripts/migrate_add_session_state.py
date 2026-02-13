from sqlalchemy import create_engine, text
from app.core.config import settings
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not found")
        return
        
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        try:
            # Check if column exists
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='consultation_history' AND column_name='session_state'"))
            if result.fetchone():
                logger.info("Column 'session_state' already exists.")
            else:
                logger.info("Adding 'session_state' column...")
                conn.execute(text("ALTER TABLE consultation_history ADD COLUMN session_state JSONB"))
                logger.info("Column added successfully.")
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            
if __name__ == "__main__":
    migrate()
