from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'contract_templates' AND column_name = 'template_variant'"))
    exists = result.fetchone()
    if not exists:
        conn.execute(text('ALTER TABLE contract_templates ADD COLUMN template_variant VARCHAR(100)'))
        conn.commit()
        print('[OK] Added template_variant column')
    else:
        print('[INFO] template_variant column already exists')
    conn.close()
