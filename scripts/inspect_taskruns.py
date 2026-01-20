#!/usr/bin/env python3
from app.database import SessionLocal
from app.models.contract import TaskRun
import json
import sys

def main():
    ids = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else [28, 29]
    s = SessionLocal()
    out = []
    for cid in ids:
        runs = s.query(TaskRun).filter(TaskRun.contract_id == cid).all()
        for r in runs:
            out.append({
                "id": r.id,
                "contract_id": r.contract_id,
                "status": r.status,
                "message": r.message,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            })
    print(json.dumps(out, ensure_ascii=False, indent=None))

if __name__ == '__main__':
    main()
