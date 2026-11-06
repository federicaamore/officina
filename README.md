<<<<<<< HEAD
# Gestionale Officina

Piccolo gestionale locale per un'officina: **entrate/uscite**, **magazzino gomme** e **stima dei prezzi di vendita**.
Tutto gira sul PC: i dati stanno nel file `officina.db` (SQLite) nella stessa cartella del programma e non vengono mai inviati in rete.

## Cosa fa

- **Riepilogo**: entrate, uscite e saldo dell'anno e del mese, grafico mensile, ripartizione per categoria, valore del magazzino e gomme da riordinare.
- **Entrate / Uscite**: registrazione movimenti (data, categoria, descrizione, importo, metodo di pagamento), filtri per mese/tipo, ricerca, esportazione CSV per il commercialista.
- **Magazzino gomme**: misura (es. 205/55 R16), marca, modello, stagione, indice, DOT, nuova/usata, quantità, scorta minima, posizione sullo scaffale.
  - **Vendi**: scala le gomme dal magazzino e registra l'incasso (con montaggio) tra le entrate.
  - **Carica**: aggiunge gomme arrivate, aggiorna il costo medio e può registrare la spesa tra le uscite.
- **Stima prezzi**: per ogni gomma propone un prezzo di vendita = costo + ricarico % (impostabile), e mostra la media dei prezzi della stessa misura e dei venduti negli ultimi 12 mesi.
- **Backup**: copia automatica giornaliera del database in `backup/` (ultimi 30 giorni, anche se il PC resta acceso per giorni) + backup manuale da Impostazioni.

## Requisiti

Solo **Python 3.8 o superiore**, nessuna libreria da installare.
Su Windows: scaricalo da <https://www.python.org/downloads/> e durante l'installazione spunta **"Add Python to PATH"**.

## Avvio automatico (consigliato)

Da fare **una volta sola**:

- **Windows**: doppio clic su `Installa avvio automatico (Windows).bat`
- **Mac**: doppio clic su `Installa avvio automatico (Mac).command` (la prima volta: tasto destro → Apri)

Da quel momento il gestionale parte da solo all'accensione del PC, senza finestre, e sul desktop compare l'icona **Gestionale Officina**.
L'indirizzo è sempre lo stesso, **http://127.0.0.1:8765**: si può salvare nei preferiti del browser.
Se si avvia il programma quando è già acceso, si apre solo la pagina (non parte una seconda copia).
Per togliere l'avvio automatico su Windows: `Rimuovi avvio automatico (Windows).bat`.

## Avvio manuale

- **Windows**: doppio clic su `Avvia Gestionale (Windows).bat`
- **Mac**: doppio clic su `Avvia Gestionale (Mac).command`
- **Da terminale**: `python app.py`

Si apre il browser su `http://127.0.0.1:8765`. Lascia aperta la finestra nera finché usi il gestionale; per chiuderlo chiudi quella finestra.
Il server ascolta solo su `127.0.0.1`, quindi non è raggiungibile da altri dispositivi della rete.

## Aggiornare il programma (GitHub)

Il repository contiene **solo il codice**: `officina.db`, `backup/` e i CSV sono esclusi da `.gitignore`, quindi i dati dell'officina non finiscono mai su GitHub.

Sul PC dell'officina, per prendere l'ultima versione:

```bash
git pull
```

I dati non vengono toccati: le tabelle si creano/aggiornano da sole all'avvio.

## Struttura

```
app.py              server locale + database SQLite (solo libreria standard)
static/index.html   interfaccia
officina.db         i dati (creato al primo avvio, NON su git)
backup/             backup automatici (NON su git)
```
=======
# officina
>>>>>>> 028c991853446e7c97d9dee01a76f28c1c7d2c12
