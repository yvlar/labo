import json
import sqlite3
from pathlib import Path
from datetime import datetime
from .data import Bar, canonical, digest, UTC

class Journal:
    """Append-only inputs, decisions and health. Restart by deterministic event replay."""
    def __init__(self,path,identity):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS identity (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS inputs (time TEXT PRIMARY KEY, payload TEXT NOT NULL, allowed INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS health (seq INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS control (id INTEGER PRIMARY KEY CHECK(id=1), halted INTEGER NOT NULL DEFAULT 0);
        INSERT OR IGNORE INTO control VALUES(1,0);
        ''')
        value=canonical(identity)
        row=self.db.execute('SELECT value FROM identity WHERE id=1').fetchone()
        if row and row[0]!=value:
            raise ValueError('Version/configuration/provenance différente : nouvelle expérience obligatoire')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO identity VALUES(1,?)',(value,))

    def restore(self,engine):
        rows=self.db.execute('SELECT payload,allowed FROM inputs ORDER BY time').fetchall()
        for payload,allowed in rows:
            engine.push(Bar.parse(json.loads(payload)),bool(allowed))
        stored=[r[0] for r in self.db.execute('SELECT payload FROM events ORDER BY seq')]
        if stored!=[canonical(e) for e in engine.events]:
            raise ValueError('Rejeu non identique : arrêt, aucune réécriture du journal')

    def append(self,engine,bar,allowed=True):
        payload=canonical(bar.record())
        row=self.db.execute('SELECT payload FROM inputs WHERE time=?',(bar.time.isoformat(),)).fetchone()
        if row:
            if row[0]!=payload:raise ValueError('Correction refusée : données prospectives immuables')
            return False
        events=engine.push(bar,allowed)
        # Input and resulting events are committed together. On storage failure caller must stop.
        with self.db:
            self.db.execute('INSERT INTO inputs VALUES(?,?,?)',(bar.time.isoformat(),payload,int(allowed)))
            self.db.executemany('INSERT INTO events VALUES(?,?)',[(e['seq'],canonical(e)) for e in events])
        return True

    def health(self,status,reason):
        with self.db:
            self.db.execute('INSERT INTO health(time,status,reason) VALUES(?,?,?)',
                            (datetime.now(UTC).isoformat(),status,reason))

    def close(self): self.db.close()

    def halted(self):
        return bool(self.db.execute('SELECT halted FROM control WHERE id=1').fetchone()[0])

    def latch_halt(self,reason):
        with self.db:
            self.db.execute('UPDATE control SET halted=1 WHERE id=1')
            self.db.execute('INSERT INTO health(time,status,reason) VALUES(?,?,?)',
                            (datetime.now(UTC).isoformat(),'HALTED',reason))
