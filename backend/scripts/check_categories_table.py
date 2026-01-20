"""检查categories表结构"""
import sys
from pathlib import Path
CURRENT_DIR = Path(__file__).parent
BACKEND_DIR = CURRENT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
cols = inspector.get_columns('categories')

print("Categories表结构:")
print("="*60)
for c in cols:
    print(f"{c['name']}: {c['type']}")
