import json
import sqlite3
from pathlib import Path
from threading import RLock


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created TEXT, data TEXT NOT NULL)')
        self.db.commit()

    def save(self, run):
        data = json.dumps(run, ensure_ascii=False, allow_nan=False)
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO runs VALUES (?, ?, ?)', (run['id'], run['created_at'], data))

    def get(self, run_id):
        with self.lock:
            row = self.db.execute('SELECT data FROM runs WHERE id=?', (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return json.loads(row[0])

    def list(self, limit=100):
        with self.lock:
            rows = self.db.execute('SELECT data FROM runs ORDER BY created DESC LIMIT ?', (limit,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def invalidate_unfinished(self):
        with self.lock:
            rows = self.db.execute('SELECT data FROM runs').fetchall()
        for row in rows:
            run = json.loads(row[0])
            if run['status'] in ('READY', 'RUNNING', 'EVALUATING'):
                run['status'] = 'STOPPED'
                run['reason'] = '프로세스 재시작: 이전 승인을 무효화했습니다.'
                self.save(run)

    def close(self):
        with self.lock:
            self.db.close()
