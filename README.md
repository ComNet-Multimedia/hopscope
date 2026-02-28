# Visual Traceroute – monitoring MTR

Graficzny monitoring ścieżki sieciowej (MTR). Kolektor co 30 s uruchamia `mtr -c 1 -j <cel>`, zapisuje wyniki do SQLite, a frontend pokazuje mapę hopów z kolorami (zielony = OK, czerwony = straty/???).

## Wymagania

- Python 3.10+
- **mtr** w PATH (np. `brew install mtr` na macOS)

## Instalacja

```bash
cd visual-traceroute
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Uruchomienie

**1. Kolektor (w tle, zapis do SQLite):**

Na **macOS** `mtr` wymaga uprawnień root — uruchom kolektor przez `sudo`:

```bash
# Domyślnie: cel google.com, co 30 s (macOS: z sudo)
sudo python backend/collector.py

# Inny cel i interwał (zmienne środowiskowe):
MTR_TARGET=8.8.8.8 MTR_INTERVAL=60 sudo python backend/collector.py
```

Na Linuxie zwykle możesz uruchomić `python backend/collector.py` bez sudo.

**2. Serwer WWW + API:**

```bash
python backend/server.py
```

Otwórz w przeglądarce: **http://localhost:5000**

**Import jednego wyniku MTR (bez kolektora):**

```bash
mtr -c 1 -j google.com | python backend/import_mtr_json.py
```

## API

- `GET /api/latest?target=google.com` – ostatni run z hubami
- `GET /api/runs?target=...&limit=50` – lista runów
- `GET /api/runs/<id>` – pojedynczy run z hubami

## Frontend

- **Network Map** – wizualizacja hopów (kropki + linie), zielony/czerwony w zależności od strat.
- **Tooltip** – po najechaniu na hop: host, Min/Avg/Max (ms), Loss%.

Dane przechowywane w `data/mtr.db` (SQLite).
