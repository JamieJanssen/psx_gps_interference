# PSX GPS Interference

Automatic GPS interference zone manager for Aerowinx PSX.

This utility uses the GPS Jamming & Spoofing functionality introduced in Aerowinx PSX and automatically activates predefined interference scenarios based on the aircraft's geographical position.

The application continuously monitors the aircraft position and loads the appropriate PSX GPS interference configuration whenever the aircraft enters a configured zone.

All GPS jamming, spoofing, drift calculations, transition behaviour and avionics effects are simulated entirely by Aerowinx PSX. This utility simply automates the activation and deactivation of PSX interference scenarios.

## Features

* Uses the native Aerowinx PSX GPS Jamming & Spoofing simulation
* Automatic zone-based activation
* Overlapping zone management
* Intermittent transition areas near zone boundaries
* Lightweight standalone Python application (.EXE available)

## How It Works

```text
Aircraft position
        ↓
PSX GPS Interference
        ↓
PSX Qs572 Scenario
        ↓
Aerowinx PSX
        ↓
GPS Jamming / Spoofing Effects
```

The utility does not simulate GPS interference itself.

Instead, it automatically configures PSX's built-in GPS Jamming & Spoofing system based on the aircraft's current location.

## Zone Database

Interference zones are stored in:

```text
psx_gps_interference.zones.txt
```

Each line defines a single PSX GPS interference scenario.

Format:

```text
NAME|TYPE|DESCRIPTION|QS572
```

Example:

```text
BALKANS_BLACKSEA_01|JAM|Balkans / Black Sea GPS interference|Pt0.746277;0.599142;0;0;100;0.872665;0.698132;80;-60;
```

### Fields

| Field       | Description                                     |
| ----------- | ----------------------------------------------- |
| NAME        | Unique zone identifier                          |
| TYPE        | User-defined category (JAM, SPOOF, MIXED, etc.) |
| DESCRIPTION | Human-readable description                      |
| QS572       | Complete PSX GPS interference configuration     |

The TYPE field is informational only and is not interpreted by the application.

### Qs572 Structure

```text
PtZONE_LAT;ZONE_LON;MIN_RADIUS;RADIUS_VARIATION;JAMMING_EXTENSION;SPOOF_LAT;SPOOF_LON;SPOOF_ALT;TIME_OFFSET;
```

| Parameter         | Description                                            |
| ----------------- | ------------------------------------------------------ |
| ZONE_LAT          | Zone centre latitude (radians)                         |
| ZONE_LON          | Zone centre longitude (radians)                        |
| MIN_RADIUS        | Minimum spoofing radius (NM)                           |
| RADIUS_VARIATION  | Additional randomized radius (NM)                      |
| JAMMING_EXTENSION | Jamming area extending beyond the spoofing radius (NM) |
| SPOOF_LAT         | Target spoofed latitude (radians)                      |
| SPOOF_LON         | Target spoofed longitude (radians)                     |
| SPOOF_ALT         | Target spoofed altitude (feet)                         |
| TIME_OFFSET       | GPS time offset (minutes)                              |

All GPS interference behaviour is simulated by Aerowinx PSX.

This application simply selects and activates the appropriate Qs572 scenario based on the aircraft's position.

### Example Zones

Jamming only:

```text
BLACKSEA_JAM_01|JAM|Black Sea GPS jamming|Pt0.754278;0.540471;0;0;150;0.872665;0.698132;80;-60;
```

Spoofing:

```text
CYPRUS_SPOOF_01|SPOOF|Eastern Mediterranean GPS spoofing|Pt0.615519;0.581776;40;0;0;0.590823;0.619388;50;0;
```

Comments may be added using:

```text
# This is a comment
```
