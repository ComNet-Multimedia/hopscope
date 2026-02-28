# HopScope

Graficzny monitoring ścieżki sieciowej (MTR). Kolektor okresowo uruchamia `mtr -c 1 -j <cel>`, zapisuje wyniki do SQLite, a frontend pokazuje mapę hopów, timeline w czasie oraz widok zbiorczy dla wybranego przedziału.

## Funkcje

- **Mapa sieci** – wizualizacja hopów (zielony / żółty / czerwony wg strat i opóźnień)
- **Timeline** – status wybranego hopu w czasie (wybór zakresu 1h–48h i hosta)
- **Widok zbiorczy** – agregacja min/max/avg dla przedziału 1h, 6h, 24h, 48h
- **Lista runów** – runy bez dolecenia do celu zaznaczone na czerwono
- **Tooltip** – po najechaniu: host, Min/Avg/Max (ms), Loss%

Dane w SQLite w katalogu `data/` (w Dockerze – wolumen).

---

## Uruchomienie w Dockerze (zalecane)

**Wymagania:** Docker i Docker Compose.

```bash
git clone git@github.com:ComNet-Multimedia/hopscope.git
cd hopscope
docker compose up -d
```

Aplikacja: **http://localhost:5000**

- **collector** – co 30 s odpala MTR do `google.com`, zapisuje do współdzielonego wolumenu
- **server** – serwuje frontend i API

Zmienne środowiskowe (opcjonalnie w `.env` lub przy `docker compose up`):

- `MTR_TARGET` – cel traceroute (domyślnie `google.com`)
- `MTR_INTERVAL` – odstęp w sekundach (domyślnie `30`)

Zatrzymanie: `docker compose down`. Dane pomiarów są w wolumenie `hopscope-data` i przetrwają `down`.

---

## Uruchomienie lokalne

**Wymagania:** Python 3.10+, **mtr** w PATH (`brew install mtr` na macOS, `apt install mtr` na Debian/Ubuntu).

```bash
cd hopscope
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**1. Kolektor (w tle):**

Na macOS `mtr` wymaga uprawnień root:

```bash
sudo python backend/collector.py
```

Na Linuxie zwykle: `python backend/collector.py`.

Zmienne: `MTR_TARGET`, `MTR_INTERVAL` (np. `MTR_TARGET=8.8.8.8 MTR_INTERVAL=60`).

**2. Serwer WWW:**

```bash
python backend/server.py
```

Aplikacja: **http://localhost:5000** (port zmienny przez `PORT`).

**Import jednego wyniku MTR (bez kolektora):**

```bash
mtr -c 1 -j google.com | python backend/import_mtr_json.py
```

---

## API

- `GET /api/latest?target=...` – ostatni run z hubami
- `GET /api/runs?target=...&limit=50` – lista runów (z `reached_destination`)
- `GET /api/runs/<id>` – pojedynczy run z hubami
- `GET /api/aggregate?from=...&to=...&target=...` – agregacja dla przedziału czasu
- `GET /api/runs_range?from=...&to=...&target=...` – runy w przedziale (z hubami, do timeline)

---

## Kolory hopów

- **Zielony** – 0% loss, czas (avg) ≤ 100 ms  
- **Żółty** – loss 0.0001–1% lub czas > 100 ms  
- **Czerwony** – loss > 1% lub host `???`
