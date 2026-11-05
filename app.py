#!/usr/bin/env python3
"""
Gestionale Officina - entrate, uscite e magazzino gomme.
Tutti i dati restano nel file officina.db accanto a questo programma.
Richiede solo Python 3.8+ (nessuna libreria esterna).
"""
import csv
import io
import json
import math
import os
import re
import sqlite3
import socket
import sys
import threading
import webbrowser
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "officina.db")
STATIC = os.path.join(BASE, "static")
BACKUP_DIR = os.path.join(BASE, "backup")
BACKUP_DA_TENERE = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS gomme (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marca TEXT NOT NULL DEFAULT '',
    modello TEXT NOT NULL DEFAULT '',
    larghezza INTEGER,
    altezza INTEGER,
    diametro INTEGER,
    indice TEXT DEFAULT '',
    stagione TEXT DEFAULT 'Estiva',
    dot TEXT DEFAULT '',
    condizione TEXT DEFAULT 'Nuova',
    quantita INTEGER NOT NULL DEFAULT 0,
    scorta_min INTEGER NOT NULL DEFAULT 0,
    costo REAL NOT NULL DEFAULT 0,
    prezzo REAL NOT NULL DEFAULT 0,
    posizione TEXT DEFAULT '',
    note TEXT DEFAULT '',
    creato TEXT DEFAULT (datetime('now','localtime')),
    aggiornato TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS movimenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('entrata','uscita')),
    categoria TEXT NOT NULL DEFAULT 'Altro',
    descrizione TEXT DEFAULT '',
    importo REAL NOT NULL,
    metodo TEXT DEFAULT 'Contanti',
    gomma_id INTEGER REFERENCES gomme(id) ON DELETE SET NULL,
    quantita INTEGER,
    prezzo_unitario REAL,
    creato TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_mov_data ON movimenti(data);
CREATE TABLE IF NOT EXISTS impostazioni (
    chiave TEXT PRIMARY KEY,
    valore TEXT
);
"""

DEFAULT_IMPOSTAZIONI = {
    "nome_officina": "Officina",
    "ricarico_percentuale": "35",
    "arrotonda_a": "1",
    "montaggio_per_gomma": "15",
    "categorie_entrata": "Riparazioni,Tagliando,Vendita gomme,Cambio gomme / montaggio,Revisione,Elettrauto,Altro",
    "categorie_uscita": "Ricambi,Acquisto gomme,Affitto,Utenze,Stipendi,Tasse / F24,Attrezzatura,Carburante,Smaltimento,Altro",
}


# ----------------------------------------------------------------- database
def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        # aggiornamenti dello schema per database creati con versioni precedenti
        colonne = {r["name"] for r in c.execute("PRAGMA table_info(movimenti)")}
        if "prezzo_unitario" not in colonne:
            c.execute("ALTER TABLE movimenti ADD COLUMN prezzo_unitario REAL")
        for k, v in DEFAULT_IMPOSTAZIONI.items():
            c.execute("INSERT OR IGNORE INTO impostazioni(chiave, valore) VALUES (?,?)", (k, v))


def backup(motivo="auto"):
    """Copia sicura del database nella cartella backup/ (una al giorno + manuali)."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    oggi = date.today().isoformat()
    if motivo == "auto":
        nome = f"officina_{oggi}.db"
        if os.path.exists(os.path.join(BACKUP_DIR, nome)):
            return nome
    else:
        nome = f"officina_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_manuale.db"
    src = conn()
    dst = sqlite3.connect(os.path.join(BACKUP_DIR, nome))
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    # tiene solo gli ultimi N backup automatici
    auto = sorted(f for f in os.listdir(BACKUP_DIR) if re.match(r"officina_\d{4}-\d{2}-\d{2}\.db$", f))
    for f in auto[:-BACKUP_DA_TENERE]:
        try:
            os.remove(os.path.join(BACKUP_DIR, f))
        except OSError:
            pass
    return nome


def impostazioni(c):
    return {r["chiave"]: r["valore"] for r in c.execute("SELECT chiave, valore FROM impostazioni")}


def num(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(str(v).replace(",", "."))
    except ValueError:
        return default


def intero(v, default=0):
    try:
        if v is None or v == "":
            return default
        return int(float(str(v).replace(",", ".")))
    except ValueError:
        return default


def misura(g):
    if not g["larghezza"] or not g["diametro"]:
        return ""
    return f"{g['larghezza']}/{g['altezza'] or ''} R{g['diametro']}"


# ----------------------------------------------------------- stima prezzi
def arrotonda(valore, passo):
    if passo <= 0:
        return round(valore, 2)
    return round(math.floor(valore / passo + 0.5) * passo, 2)  # arrotonda per eccesso a .5


def gomme_con_stima(c):
    imp = impostazioni(c)
    ricarico = num(imp.get("ricarico_percentuale"), 35)
    passo = num(imp.get("arrotonda_a"), 1)
    righe = [dict(r) for r in c.execute("SELECT * FROM gomme ORDER BY diametro, larghezza, altezza, marca")]

    # prezzi a listino per misura (stessa stagione)
    listino = {}
    for g in righe:
        if g["prezzo"] > 0:
            listino.setdefault((g["larghezza"], g["altezza"], g["diametro"], g["stagione"]), []).append(g["prezzo"])

    # prezzi di vendita reali degli ultimi 12 mesi per misura
    venduto = {}
    for r in c.execute(
        """SELECT g.larghezza, g.altezza, g.diametro, g.stagione, m.prezzo_unitario
           FROM movimenti m JOIN gomme g ON g.id = m.gomma_id
           WHERE m.tipo='entrata' AND m.prezzo_unitario > 0 AND m.data >= date('now','-12 months')"""
    ):
        venduto.setdefault((r["larghezza"], r["altezza"], r["diametro"], r["stagione"]), []).append(
            r["prezzo_unitario"]
        )

    for g in righe:
        chiave = (g["larghezza"], g["altezza"], g["diametro"], g["stagione"])
        g["misura"] = misura(g)
        g["prezzo_suggerito"] = arrotonda(g["costo"] * (1 + ricarico / 100), passo) if g["costo"] > 0 else None
        altri = [p for p in listino.get(chiave, [])]
        if g["prezzo"] > 0 and g["prezzo"] in altri:
            altri.remove(g["prezzo"])
        g["media_listino_misura"] = round(sum(altri) / len(altri), 2) if altri else None
        v = venduto.get(chiave, [])
        g["media_venduto_misura"] = round(sum(v) / len(v), 2) if v else None
        g["vendite_misura"] = len(v)
        g["margine"] = round(g["prezzo"] - g["costo"], 2) if g["prezzo"] > 0 else None
        g["sotto_scorta"] = g["scorta_min"] > 0 and g["quantita"] <= g["scorta_min"]
    return righe


# ------------------------------------------------------------- riepilogo
def riepilogo(c, anno):
    mesi = []
    for m in range(1, 13):
        pref = f"{anno}-{m:02d}"
        r = c.execute(
            """SELECT COALESCE(SUM(CASE WHEN tipo='entrata' THEN importo END),0) e,
                      COALESCE(SUM(CASE WHEN tipo='uscita' THEN importo END),0) u
               FROM movimenti WHERE substr(data,1,7)=?""",
            (pref,),
        ).fetchone()
        mesi.append({"mese": m, "entrate": round(r["e"], 2), "uscite": round(r["u"], 2)})
    cat = [
        dict(r)
        for r in c.execute(
            """SELECT tipo, categoria, ROUND(SUM(importo),2) totale, COUNT(*) n
               FROM movimenti WHERE substr(data,1,4)=? GROUP BY tipo, categoria ORDER BY totale DESC""",
            (str(anno),),
        )
    ]
    mag = c.execute(
        """SELECT COALESCE(SUM(quantita),0) pezzi,
                  COALESCE(SUM(quantita*costo),0) valore_costo,
                  COALESCE(SUM(quantita*prezzo),0) valore_vendita,
                  COUNT(*) articoli
           FROM gomme WHERE quantita > 0"""
    ).fetchone()
    sotto = [
        {"id": r["id"], "descrizione": f"{r['marca']} {r['modello']} {misura(r)}".strip(), "quantita": r["quantita"],
         "scorta_min": r["scorta_min"]}
        for r in c.execute("SELECT * FROM gomme WHERE scorta_min > 0 AND quantita <= scorta_min ORDER BY quantita")
    ]
    anni = [r[0] for r in c.execute("SELECT DISTINCT substr(data,1,4) FROM movimenti ORDER BY 1 DESC")]
    tot_e = sum(m["entrate"] for m in mesi)
    tot_u = sum(m["uscite"] for m in mesi)
    return {
        "anno": anno,
        "anni": anni,
        "mesi": mesi,
        "totale_entrate": round(tot_e, 2),
        "totale_uscite": round(tot_u, 2),
        "saldo": round(tot_e - tot_u, 2),
        "categorie": cat,
        "magazzino": {k: round(mag[k], 2) for k in mag.keys()},
        "sotto_scorta": sotto,
    }


# ------------------------------------------------------------------ HTTP
CAMPI_GOMMA = ["marca", "modello", "larghezza", "altezza", "diametro", "indice", "stagione", "dot", "condizione",
               "quantita", "scorta_min", "costo", "prezzo", "posizione", "note"]
CAMPI_INT = {"larghezza", "altezza", "diametro", "quantita", "scorta_min"}
CAMPI_NUM = {"costo", "prezzo"}


def pulisci_gomma(d):
    out = {}
    for k in CAMPI_GOMMA:
        if k not in d:
            continue
        v = d[k]
        if k in CAMPI_INT:
            out[k] = intero(v) if v not in (None, "") else None
            if k in ("quantita", "scorta_min"):
                out[k] = max(0, out[k] or 0)
        elif k in CAMPI_NUM:
            out[k] = max(0.0, num(v))
        else:
            out[k] = str(v or "").strip()
    return out


def pulisci_movimento(d):
    tipo = d.get("tipo")
    if tipo not in ("entrata", "uscita"):
        raise ValueError("Tipo non valido")
    data = str(d.get("data") or date.today().isoformat())[:10]
    datetime.strptime(data, "%Y-%m-%d")
    importo = num(d.get("importo"))
    if importo <= 0:
        raise ValueError("L'importo deve essere maggiore di zero")
    return {
        "tipo": tipo,
        "data": data,
        "categoria": str(d.get("categoria") or "Altro").strip(),
        "descrizione": str(d.get("descrizione") or "").strip(),
        "importo": round(importo, 2),
        "metodo": str(d.get("metodo") or "Contanti").strip(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "GestionaleOfficina/1.0"

    def log_message(self, fmt, *args):  # silenzioso
        pass

    # -- utilità
    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def errore(self, msg, status=400):
        self.send_json({"errore": msg}, status)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def dispatch(self, metodo):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        path = url.path.rstrip("/") or "/"
        try:
            if not path.startswith("/api"):
                if metodo == "GET":
                    return self.statico(path)
                return self.errore("Non trovato", 404)
            for pattern, m, fn in ROUTES:
                if m != metodo:
                    continue
                mm = re.fullmatch(pattern, path)
                if mm:
                    return fn(self, q, *mm.groups())
            self.errore("Non trovato", 404)
        except (ValueError, KeyError) as e:
            self.errore(str(e))
        except Exception as e:  # noqa
            self.errore(f"Errore interno: {e}", 500)

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def statico(self, path):
        if path == "/":
            path = "/index.html"
        file = os.path.normpath(os.path.join(STATIC, path.lstrip("/")))
        if not file.startswith(STATIC) or not os.path.isfile(file):
            return self.errore("Non trovato", 404)
        tipi = {".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".svg": "image/svg+xml"}
        with open(file, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", tipi.get(os.path.splitext(file)[1], "application/octet-stream") + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # -- movimenti
    def get_movimenti(self, q):
        sql = """SELECT m.*, g.marca, g.modello, g.larghezza, g.altezza, g.diametro
                 FROM movimenti m LEFT JOIN gomme g ON g.id = m.gomma_id WHERE 1=1"""
        args = []
        if q.get("mese"):
            sql += " AND substr(m.data,1,7)=?"
            args.append(q["mese"])
        elif q.get("anno"):
            sql += " AND substr(m.data,1,4)=?"
            args.append(q["anno"])
        if q.get("tipo") in ("entrata", "uscita"):
            sql += " AND m.tipo=?"
            args.append(q["tipo"])
        if q.get("cerca"):
            sql += " AND (m.descrizione LIKE ? OR m.categoria LIKE ?)"
            args += [f"%{q['cerca']}%"] * 2
        sql += " ORDER BY m.data DESC, m.id DESC"
        with conn() as c:
            righe = [dict(r) for r in c.execute(sql, args)]
        self.send_json(righe)

    def post_movimento(self, q):
        m = pulisci_movimento(self.body())
        with conn() as c:
            cur = c.execute(
                "INSERT INTO movimenti(data,tipo,categoria,descrizione,importo,metodo) VALUES (:data,:tipo,:categoria,:descrizione,:importo,:metodo)",
                m,
            )
        self.send_json({"id": cur.lastrowid}, 201)

    def put_movimento(self, q, mid):
        m = pulisci_movimento(self.body())
        m["id"] = int(mid)
        with conn() as c:
            c.execute(
                "UPDATE movimenti SET data=:data,tipo=:tipo,categoria=:categoria,descrizione=:descrizione,importo=:importo,metodo=:metodo WHERE id=:id",
                m,
            )
        self.send_json({"ok": True})

    def delete_movimento(self, q, mid):
        with conn() as c:
            c.execute("DELETE FROM movimenti WHERE id=?", (int(mid),))
        self.send_json({"ok": True})

    def export_csv(self, q):
        with conn() as c:
            sql = "SELECT data,tipo,categoria,descrizione,importo,metodo FROM movimenti"
            args = []
            if q.get("anno"):
                sql += " WHERE substr(data,1,4)=?"
                args.append(q["anno"])
            righe = c.execute(sql + " ORDER BY data", args).fetchall()
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["Data", "Tipo", "Categoria", "Descrizione", "Importo", "Metodo"])
        for r in righe:
            w.writerow([r["data"], r["tipo"], r["categoria"], r["descrizione"],
                        f"{r['importo']:.2f}".replace(".", ","), r["metodo"]])
        data = ("\ufeff" + buf.getvalue()).encode("utf-8")  # BOM: Excel legge gli accenti
        nome = f"movimenti_{q.get('anno', 'tutti')}.csv"
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{nome}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # -- gomme
    def get_gomme(self, q):
        with conn() as c:
            self.send_json(gomme_con_stima(c))

    def post_gomma(self, q):
        g = pulisci_gomma(self.body())
        if not g.get("marca") and not g.get("larghezza"):
            raise ValueError("Inserisci almeno marca o misura")
        cols = ",".join(g.keys())
        ph = ",".join(":" + k for k in g.keys())
        with conn() as c:
            cur = c.execute(f"INSERT INTO gomme({cols}) VALUES ({ph})", g)
        self.send_json({"id": cur.lastrowid}, 201)

    def put_gomma(self, q, gid):
        g = pulisci_gomma(self.body())
        if not g:
            raise ValueError("Nessun dato")
        sets = ",".join(f"{k}=:{k}" for k in g.keys())
        g["id"] = int(gid)
        with conn() as c:
            c.execute(f"UPDATE gomme SET {sets}, aggiornato=datetime('now','localtime') WHERE id=:id", g)
        self.send_json({"ok": True})

    def delete_gomma(self, q, gid):
        with conn() as c:
            c.execute("DELETE FROM gomme WHERE id=?", (int(gid),))
        self.send_json({"ok": True})

    def _gomma(self, c, gid):
        g = c.execute("SELECT * FROM gomme WHERE id=?", (int(gid),)).fetchone()
        if not g:
            raise ValueError("Gomma non trovata")
        return g

    def vendi_gomma(self, q, gid):
        d = self.body()
        qta = intero(d.get("quantita"), 0)
        if qta <= 0:
            raise ValueError("Quantità non valida")
        with conn() as c:
            g = self._gomma(c, gid)
            if qta > g["quantita"]:
                raise ValueError(f"In magazzino ce ne sono solo {g['quantita']}")
            c.execute("UPDATE gomme SET quantita=quantita-?, aggiornato=datetime('now','localtime') WHERE id=?", (qta, g["id"]))
            if d.get("registra", True):
                totale = round(num(d.get("totale")), 2)
                if totale <= 0:
                    raise ValueError("Inserisci il totale incassato")
                desc = f"{qta}× {g['marca']} {g['modello']} {misura(g)}".strip()
                if d.get("cliente"):
                    desc += f" - {d['cliente']}"
                pu = num(d.get("prezzo_unitario")) or None  # prezzo della sola gomma, senza montaggio
                c.execute(
                    "INSERT INTO movimenti(data,tipo,categoria,descrizione,importo,metodo,gomma_id,quantita,prezzo_unitario) VALUES (?,?,?,?,?,?,?,?,?)",
                    (d.get("data") or date.today().isoformat(), "entrata", "Vendita gomme", desc, totale,
                     d.get("metodo") or "Contanti", g["id"], qta, pu),
                )
        self.send_json({"ok": True})

    def carica_gomma(self, q, gid):
        d = self.body()
        qta = intero(d.get("quantita"), 0)
        if qta <= 0:
            raise ValueError("Quantità non valida")
        costo = num(d.get("costo_unitario"))
        with conn() as c:
            g = self._gomma(c, gid)
            nuovo_costo = g["costo"]
            if costo > 0:  # costo medio ponderato
                tot = g["quantita"] + qta
                nuovo_costo = round((g["quantita"] * g["costo"] + qta * costo) / tot, 2) if tot else costo
            c.execute(
                "UPDATE gomme SET quantita=quantita+?, costo=?, aggiornato=datetime('now','localtime') WHERE id=?",
                (qta, nuovo_costo, g["id"]),
            )
            if d.get("registra") and costo > 0:
                desc = f"Acquisto {qta}× {g['marca']} {g['modello']} {misura(g)}".strip()
                if d.get("fornitore"):
                    desc += f" - {d['fornitore']}"
                c.execute(
                    "INSERT INTO movimenti(data,tipo,categoria,descrizione,importo,metodo,gomma_id,quantita) VALUES (?,?,?,?,?,?,?,?)",
                    (d.get("data") or date.today().isoformat(), "uscita", "Acquisto gomme", desc,
                     round(qta * costo, 2), d.get("metodo") or "Bonifico", g["id"], -qta),
                )
        self.send_json({"ok": True})

    # -- riepilogo / impostazioni / backup
    def get_riepilogo(self, q):
        anno = intero(q.get("anno"), date.today().year)
        with conn() as c:
            self.send_json(riepilogo(c, anno))

    def get_impostazioni(self, q):
        with conn() as c:
            imp = impostazioni(c)
        imp["_percorso_db"] = DB
        imp["_percorso_backup"] = BACKUP_DIR
        self.send_json(imp)

    def put_impostazioni(self, q):
        d = self.body()
        with conn() as c:
            for k, v in d.items():
                if k in DEFAULT_IMPOSTAZIONI:
                    c.execute("INSERT OR REPLACE INTO impostazioni(chiave,valore) VALUES (?,?)", (k, str(v)))
        self.send_json({"ok": True})

    def post_backup(self, q):
        nome = backup("manuale")
        self.send_json({"ok": True, "file": os.path.join(BACKUP_DIR, nome)})


ROUTES = [
    (r"/api/movimenti", "GET", Handler.get_movimenti),
    (r"/api/movimenti", "POST", Handler.post_movimento),
    (r"/api/movimenti/(\d+)", "PUT", Handler.put_movimento),
    (r"/api/movimenti/(\d+)", "DELETE", Handler.delete_movimento),
    (r"/api/export/movimenti\.csv", "GET", Handler.export_csv),
    (r"/api/gomme", "GET", Handler.get_gomme),
    (r"/api/gomme", "POST", Handler.post_gomma),
    (r"/api/gomme/(\d+)", "PUT", Handler.put_gomma),
    (r"/api/gomme/(\d+)", "DELETE", Handler.delete_gomma),
    (r"/api/gomme/(\d+)/vendi", "POST", Handler.vendi_gomma),
    (r"/api/gomme/(\d+)/carica", "POST", Handler.carica_gomma),
    (r"/api/riepilogo", "GET", Handler.get_riepilogo),
    (r"/api/impostazioni", "GET", Handler.get_impostazioni),
    (r"/api/impostazioni", "PUT", Handler.put_impostazioni),
    (r"/api/backup", "POST", Handler.post_backup),
]


def porta_libera(start=8765):
    for p in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise RuntimeError("Nessuna porta libera")


def main():
    init_db()
    backup("auto")
    porta = porta_libera()
    # 127.0.0.1 = raggiungibile solo da questo PC
    server = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    url = f"http://127.0.0.1:{porta}/"
    print("=" * 56)
    print("  GESTIONALE OFFICINA avviato")
    print(f"  Indirizzo: {url}")
    print(f"  Dati salvati in: {DB}")
    print("  Per chiudere: chiudi questa finestra (o CTRL+C)")
    print("=" * 56)
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
