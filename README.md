# SpaceAPI Client für Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Tests](https://github.com/dk1sel/ha-spaceapi/actions/workflows/tests.yml/badge.svg)](https://github.com/dk1sel/ha-spaceapi/actions/workflows/tests.yml)

[Deutsch](#deutsch) · [English](#english)

---

## Deutsch

Diese Custom-Integration holt alle Daten eines Hackerspaces über die [SpaceAPI](https://spaceapi.io/)
und stellt sie in Home Assistant als Entitäten bereit: Offen/Zu, Statusmeldung, alle Sensorwerte
(Temperatur, Luftfeuchte, CO₂, Strom, Wind, Personen vor Ort, Getränkevorrat …), Kontaktdaten,
Webcams und den Standort auf der Karte.

> **Hinweis:** Die Domain ist `spaceapi_client`. Sie ist bewusst getrennt von der eingebauten
> Home-Assistant-Integration [`spaceapi`](https://www.home-assistant.io/integrations/spaceapi/),
> die den *eigenen* Space veröffentlicht. Beide können parallel genutzt werden.

### Installation über HACS (Custom Repository)

1. In Home Assistant **HACS** öffnen.
2. Oben rechts auf **⋮ → Benutzerdefinierte Repositories** klicken.
3. Als Repository `https://github.com/dk1sel/ha-spaceapi` eintragen, als Typ **Integration** wählen und **Hinzufügen** klicken.
4. In HACS nach **SpaceAPI Client** suchen, öffnen und **Herunterladen** klicken.
5. Home Assistant **neu starten**.
6. **Einstellungen → Geräte & Dienste → Integration hinzufügen → SpaceAPI Client**.

Manuell geht es auch: den Ordner `custom_components/spaceapi_client` in das Verzeichnis
`config/custom_components/` von Home Assistant kopieren und neu starten.

### Einrichtung

1. **Suche** – einen Teil des Space-Namens eingeben (z. B. `chaos`). Die Integration durchsucht das
   offizielle Verzeichnis [directory.spaceapi.io](https://directory.spaceapi.io/), Groß-/Kleinschreibung
   ist egal. Alternativ direkt eine **eigene SpaceAPI-URL** eintragen.
2. **Auswahl** – den gewünschten Space aus der Liste wählen. Die API-URL wird automatisch übernommen.
3. Die URL wird abgerufen und geprüft; der Eintrag heißt wie der Space.

Mehrere Spaces sind möglich – jeder bekommt ein eigenes Gerät. Unter **Konfigurieren** lässt sich das
Abrufintervall einstellen (Standard 5 Minuten, mindestens 1 Minute).

### Entitäten

| Entität | Inhalt |
|---|---|
| `binary_sensor.<space>_geoffnet` | Offen/Zu (`state.open`), Attribute `message`, `lastchange`, `trigger_person`, Bild = Status-Icon bzw. Logo |
| `sensor.<space>_statusmeldung`, `…_letzte_statusanderung` | `state.message`, `state.lastchange` (Zeitstempel) |
| Sensoren aus dem `sensors`-Block | je Messpunkt eine Entität mit passender Geräteklasse/Einheit, Name aus `location`/`name` – temperature, humidity, carbondioxide, barometer, radiation, power_consumption, power_generation, wind, network_connections, network_traffic, account_balance, total_member_count, people_now_present, beverage_supply |
| `binary_sensor.<space>_turschloss_…` | `door_locked` (Geräteklasse Schloss: *an* = entriegelt) |
| `device_tracker.<space>_standort` | Standort auf der Karte (`location.lat`/`lon`) |
| `camera.<space>_webcam_N` | Webcams aus `cam` (Standbild) |
| Diagnose-Sensoren | Webseite (mit Logo), Adresse, API-Version, Kontakte (E-Mail, Telefon, Matrix, Mastodon, IRC, XMPP …), Feeds, Projekte, Links, Keymaster, letztes Ereignis |

Neue Messpunkte, die später in der API auftauchen, werden automatisch ergänzt. Fällt ein Wert weg,
wird die Entität „nicht verfügbar“. Ist die API nicht erreichbar, sind alle Entitäten des Spaces
„nicht verfügbar“, bis der nächste Abruf klappt.

### Ereignis `spaceapi_state_changed`

Wechselt ein Space zwischen offen und zu, feuert die Integration ein Ereignis (nicht beim ersten Abruf):

```yaml
event_type: spaceapi_state_changed
data:
  entry_id: "…"
  space: "Mein Hackspace"
  url: "https://example.org/spaceapi.json"
  open: true
  previous: false
```

Beispiel-Automation:

```yaml
triggers:
  - trigger: event
    event_type: spaceapi_state_changed
    event_data:
      open: true
actions:
  - action: notify.notify
    data:
      message: "{{ trigger.event.data.space }} ist jetzt offen!"
```

### Unterstützte API-Versionen

SpaceAPI **v15** und **v14** werden vollständig unterstützt (`api_compatibility`). Ältere Formate
(v0.13 mit `api`, v0.12 mit `open`/`status`/`icon`/`lat`/`lon` auf oberster Ebene) werden so gut wie
möglich gelesen.

### Diagnose

Unter **Geräte & Dienste → SpaceAPI Client → ⋮ → Diagnose herunterladen** gibt es die Roh-Antwort der API.

### Entwicklung

```bash
pip install -r requirements_test.txt
pytest
```

Die Tests laufen unter Linux/macOS (bzw. in GitHub Actions). Home Assistant selbst unterstützt
Windows nicht.

---

## English

This custom integration pulls everything a hackerspace publishes via the [SpaceAPI](https://spaceapi.io/)
into Home Assistant: open/closed state, status message, every sensor value (temperature, humidity,
CO₂, power, wind, people present, beverage supply …), contact details, webcams and the location on
the map.

> **Note:** The domain is `spaceapi_client`, deliberately separate from Home Assistant's built-in
> [`spaceapi`](https://www.home-assistant.io/integrations/spaceapi/) integration (which *publishes*
> your own space). Both can be used side by side.

### Installation via HACS (custom repository)

1. Open **HACS** in Home Assistant.
2. Click **⋮ → Custom repositories** (top right).
3. Enter `https://github.com/dk1sel/ha-spaceapi`, choose type **Integration**, click **Add**.
4. Search HACS for **SpaceAPI Client**, open it and click **Download**.
5. **Restart** Home Assistant.
6. **Settings → Devices & services → Add integration → SpaceAPI Client**.

Manual installation: copy `custom_components/spaceapi_client` into Home Assistant's
`config/custom_components/` folder and restart.

### Setup

1. **Search** – type part of the space name (e.g. `chaos`). The official directory
   [directory.spaceapi.io](https://directory.spaceapi.io/) is searched case-insensitively. Or enter
   **your own SpaceAPI URL** directly.
2. **Select** – pick the space from the dropdown; its API URL is filled in automatically.
3. The URL is fetched and validated; the entry is named after the space.

You can add several spaces – each one becomes its own device. **Configure** lets you change the
polling interval (default 5 minutes, minimum 1 minute).

### Entities

| Entity | Content |
|---|---|
| `binary_sensor.<space>_open` | open/closed (`state.open`), attributes `message`, `lastchange`, `trigger_person`; picture = state icon or logo |
| `sensor.<space>_status_message`, `…_last_status_change` | `state.message`, `state.lastchange` (timestamp) |
| Sensors from the `sensors` block | one entity per measurement with matching device class/unit, named after `location`/`name` |
| `binary_sensor.<space>_door_lock_…` | `door_locked` (lock device class: *on* = unlocked) |
| `device_tracker.<space>_location` | location on the map |
| `camera.<space>_webcam_N` | webcams from `cam` (still image) |
| Diagnostic sensors | website (with logo), address, API version, contacts, feeds, projects, links, keymasters, last event |

Measurements that show up later are added automatically; ones that disappear become unavailable.
If the API cannot be reached, all entities of that space are unavailable until the next successful
update.

### Event `spaceapi_state_changed`

Fired when a space switches between open and closed (never on the first update). Event data:
`entry_id`, `space`, `url`, `open`, `previous`.

### Supported API versions

SpaceAPI **v15** and **v14** are fully supported. Older formats (v0.13, v0.12) are read on a
best-effort basis.

### Diagnostics

**Devices & services → SpaceAPI Client → ⋮ → Download diagnostics** contains the raw API response.

### Development

```bash
pip install -r requirements_test.txt
pytest
```

## License

MIT – see [LICENSE](LICENSE).
