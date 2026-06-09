# psx_gps_interference.py
# Live GPS jamming/spoofing zone manager for Aerowinx PSX
#
# Reads aircraft position from PSX Qs121 and automatically sends Qs572
# when the aircraft enters a configured GPS interference zone.
#
# Files:
#   psx_gps_interference.ini        PSX network settings only
#   psx_gps_interference.zones.txt  Zone database
#
# Zone format:
#   NAME|TYPE|DESCRIPTION|QS572
#
# Example:
#   BALKANS_BLACKSEA_01|JAM|Balkans / Black Sea GPS interference|Pt0.746277;0.599142;0;0;100;0.872665;0.698132;80;-60;

import argparse
import configparser
import math
import os
import select
import socket
import time
import random
from dataclasses import dataclass
from pathlib import Path

VERSION = "1.00"
APP_NAME = "PSX GPS Interference"
BASE_NAME = "psx_gps_interference"
INI_FILE = f"{BASE_NAME}.ini"
ZONES_FILE = f"{BASE_NAME}.zones.txt"

OFF_QS572 = "pt0;0;0;0;0;0;0;0;0;"
DEFAULT_TRANSITION_BAND_PERCENT = 5.0
DEFAULT_TRANSITION_MIN_SECONDS = 10.0
EARTH_RADIUS_NM = 3440.065


@dataclass
class Zone:
    name: str
    zone_type: str
    description: str
    qs572: str
    center_lat_rad: float
    center_lon_rad: float
    spoof_min_radius_nm: float
    radius_variation_nm: float
    jamming_extension_nm: float

    @property
    def max_effect_radius_nm(self) -> float:
        """Maximum possible area affected by this PSX scenario."""
        return max(
            0.0,
            self.spoof_min_radius_nm
            + self.radius_variation_nm
            + self.jamming_extension_nm,
        )


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_header() -> None:
    print(
        f"""
============================================================
                {APP_NAME} v{VERSION}
    GPS Jamming & Spoofing Zone Manager for Aerowinx PSX
                   Jamie Janssen © 2026
============================================================
""".strip()
    )


def ensure_files() -> None:
    ini_path = Path(INI_FILE)
    zones_path = Path(ZONES_FILE)

    if not ini_path.exists():
        ini_path.write_text(
            "[PSX]\n"
            "host = 127.0.0.1\n"
            "port = 10747\n",
            encoding="utf-8",
        )

    if not zones_path.exists():
        zones_path.write_text(
            "# PSX GPS Interference zones\n"
            "# Format:\n"
            "# NAME|TYPE|DESCRIPTION|QS572\n"
            "#\n"
            "# Qs572 format:\n"
            "# PtZONE_LAT_RAD;ZONE_LON_RAD;SPOOF_MIN_RADIUS_NM;RADIUS_VARIATION_NM;JAMMING_EXTENSION_NM;SPOOF_TO_LAT_RAD;SPOOF_TO_LON_RAD;SPOOF_ALT_FT;TIME_OFFSET_MIN;\n"
            "#\n"
            "# Black Sea example, based on N42 45.5 E034 19.7\n"
            "BALKANS_BLACKSEA_01|JAM|Balkans / Black Sea GPS interference|Pt0.746277;0.599142;0;0;100;0.872665;0.698132;80;-60;\n",
            encoding="utf-8",
        )


def read_config() -> tuple[str, int, float, float]:
    ensure_files()

    config = configparser.ConfigParser()
    config.read(INI_FILE, encoding="utf-8")

    host = config.get("PSX", "host", fallback="127.0.0.1")
    port = config.getint("PSX", "port", fallback=10747)

    transition_band_percent = config.getfloat(
        "INTERFERENCE",
        "transition_band_percent",
        fallback=DEFAULT_TRANSITION_BAND_PERCENT,
    )

    transition_min_seconds = config.getfloat(
        "INTERFERENCE",
        "transition_min_seconds",
        fallback=DEFAULT_TRANSITION_MIN_SECONDS,
    )

    transition_band_percent = max(0.0, transition_band_percent)
    transition_min_seconds = max(0.0, transition_min_seconds)

    return host, port, transition_band_percent, transition_min_seconds


def parse_qs572(qs572: str) -> tuple[float, float, float, float, float]:
    if len(qs572) < 3:
        raise ValueError("Qs572 string too short")

    payload = qs572[2:]
    values = [v for v in payload.split(";") if v != ""]

    if len(values) < 9:
        raise ValueError("Qs572 must contain 9 numeric values after Pt/pt/PT/pT")

    zone_lat_rad = float(values[0])
    zone_lon_rad = float(values[1])
    spoof_min_radius_nm = float(values[2])
    radius_variation_nm = float(values[3])
    jamming_extension_nm = float(values[4])

    return (
        zone_lat_rad,
        zone_lon_rad,
        spoof_min_radius_nm,
        radius_variation_nm,
        jamming_extension_nm,
    )


def load_zones() -> list[Zone]:
    ensure_files()
    zones: list[Zone] = []

    for line_number, raw_line in enumerate(Path(ZONES_FILE).read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        parts = line.split("|", 3)

        if len(parts) != 4:
            print(f"Ignoring invalid zone line {line_number}: {raw_line}")
            continue

        name, zone_type, description, qs572 = [part.strip() for part in parts]

        try:
            (
                center_lat_rad,
                center_lon_rad,
                spoof_min_radius_nm,
                radius_variation_nm,
                jamming_extension_nm,
            ) = parse_qs572(qs572)
        except ValueError as exc:
            print(f"Ignoring zone line {line_number} ({name}): {exc}")
            continue

        zones.append(
            Zone(
                name=name,
                zone_type=zone_type.upper(),
                description=description,
                qs572=qs572,
                center_lat_rad=center_lat_rad,
                center_lon_rad=center_lon_rad,
                spoof_min_radius_nm=spoof_min_radius_nm,
                radius_variation_nm=radius_variation_nm,
                jamming_extension_nm=jamming_extension_nm,
            )
        )

    return zones


def connect_with_retry(host: str, port: int) -> socket.socket:
    while True:
        sock = None

        try:
            print(f"Connecting to PSX on {host}:{port}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            print("Connected to PSX")
            return sock

        except KeyboardInterrupt:
            if sock:
                sock.close()
            raise

        except OSError as exc:
            print(f"PSX not available: {exc}")
            print("Retrying in 5 seconds...\n")
            if sock:
                sock.close()
            time.sleep(5)


def psx_send(sock: socket.socket, line: str) -> bool:
    try:
        sock.sendall((line.rstrip("\n") + "\n").encode("utf-8"))
        return True
    except OSError:
        return False


def parse_qs121(line: str) -> dict | None:
    if not line.startswith("Qs121="):
        return None

    values = line.split("=", 1)[1].split(";")

    if len(values) < 7:
        return None

    try:
        heading_deg = round(math.degrees(float(values[2])) % 360.0, 1)
        altitude_ft = int(values[3]) / 1000.0
        latitude_rad = float(values[5])
        longitude_rad = float(values[6])
    except ValueError:
        return None

    return {
        "lat_rad": latitude_rad,
        "lon_rad": longitude_rad,
        "lat_deg": math.degrees(latitude_rad),
        "lon_deg": math.degrees(longitude_rad),
        "altitude_ft": altitude_ft,
        "heading_deg": heading_deg,
    }


def distance_nm(lat1_rad: float, lon1_rad: float, lat2_rad: float, lon2_rad: float) -> float:
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2.0) ** 2
    )

    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_NM * c


def set_qs572_enabled(qs572: str, enabled: bool) -> str:
    """Enable/disable the PSX interference scenario.

    ON keeps the first two flags exactly as configured in the zones file
    (for example Pt or PT).

    OFF always sends pt, because in PSX a pT combination may leave GPS
    interference active.
    """
    if not qs572:
        return qs572

    if enabled:
        return qs572

    if len(qs572) >= 2:
        return "pt" + qs572[2:]

    return "pt"


def find_zone_candidate(
    position: dict,
    zones: list[Zone],
    transition_band_percent: float,
) -> tuple[Zone | None, float | None, str, list[tuple[Zone, float, str]]]:
    """
    Return the best relevant zone and state.

    Overlap priority:
      1. ACTIVE zones win over TRANSITION zones.
      2. Within the same state, nearest to zone center wins.
      3. If still equal, the earlier line in the zones file wins.

    State:
      ACTIVE      inside radius - transition band
      TRANSITION  outer edge inside the configured radius
      OFF         outside the configured radius
    """
    candidates: list[tuple[int, float, int, Zone, str]] = []
    overlaps: list[tuple[Zone, float, str]] = []
    band = max(0.0, transition_band_percent) / 100.0

    for order, zone in enumerate(zones):
        radius = zone.max_effect_radius_nm

        if radius <= 0:
            continue

        dist = distance_nm(
            position["lat_rad"],
            position["lon_rad"],
            zone.center_lat_rad,
            zone.center_lon_rad,
        )

        inner_radius = radius * max(0.0, 1.0 - band)

        if dist <= inner_radius:
            state = "ACTIVE"
            state_priority = 0
        elif dist <= radius:
            state = "TRANSITION"
            state_priority = 1
        else:
            continue

        candidates.append((state_priority, dist, order, zone, state))
        overlaps.append((zone, dist, state))

    if not candidates:
        return None, None, "OFF", []

    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    _, dist, _, zone, state = candidates[0]
    return zone, dist, state, overlaps


def print_status(
    psx_host: str,
    psx_port: int,
    zones: list[Zone],
    position: dict | None,
    active_zone: Zone | None,
    active_distance_nm: float | None,
    last_sent_name: str,
    zone_state: str,
    transition_enabled: bool | None,
    transition_band_percent: float,
    transition_min_seconds: float,
    qi277_status: str,
    qi276_radius: str,
    qs573_drift: str,
    debug: bool = False,
    overlapping_zones: list[tuple[Zone, float, str]] | None = None,
) -> None:
    clear_screen()
    print_header()
    print(f"PSX: {psx_host}:{psx_port}    Zones loaded: {len(zones)}")
    print()

    if position:
        print(
            f"Aircraft: LAT {position['lat_deg']:.6f}  "
            f"LON {position['lon_deg']:.6f}  "
            f"HDG {position['heading_deg']:.1f}  "
            f"ALT {position['altitude_ft']:.0f} ft"
        )
    else:
        print("Aircraft: waiting for Qs121...")

    if active_zone:
        print(
            f"Zone:     {active_zone.name} ({active_zone.zone_type})  "
            f"{active_distance_nm:.0f}/{active_zone.max_effect_radius_nm:.0f} nm"
        )
        print(f"          {active_zone.description}")
    else:
        print("Zone:     none")

    if overlapping_zones:
        other_overlaps = [
            f"{zone.name} {state} {dist:.0f}nm"
            for zone, dist, state in overlapping_zones
            if not active_zone or zone.name != active_zone.name
        ]
        if other_overlaps:
            print("Overlap:  " + ", ".join(other_overlaps[:3]))
            if len(other_overlaps) > 3:
                print(f"          +{len(other_overlaps) - 3} more")

    print(f"Sent:     {last_sent_name}")
    if zone_state == "TRANSITION":
        status = "ON" if transition_enabled else "OFF"
        print(f"Edge:     TRANSITION {status}  (+/-{transition_band_percent:.1f}% band, min {transition_min_seconds:.0f}s)")
    else:
        print(f"Edge:     {zone_state}")
    if debug:
        print()
        print("[DEBUG]")
        print(f"PSX Qi277 SpoofStatus: {qi277_status}")
        print(f"PSX Qi276 SpoofRadius: {qi276_radius}")
        print(f"PSX Qs573 GPS Drift:   {qs573_drift}")

    print()
    print("Press Ctrl+C to stop")


def main() -> None:
    parser = argparse.ArgumentParser(description="PSX GPS Interference")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show PSX debug values if received from PSX, such as Qi276, Qi277, and Qs573",
    )
    args = parser.parse_args()

    psx_host, psx_port, transition_band_percent, transition_min_seconds = read_config()
    zones = load_zones()

    clear_screen()
    print_header()

    if not zones:
        print(f"No zones found in {ZONES_FILE}")
        return

    psx = connect_with_retry(psx_host, psx_port)
    psx.setblocking(False)

    psx_send(psx, "clientName=PSX GPS Interference")

    buffer = ""
    latest_position = None
    current_zone_name = "OFF"
    current_enabled: bool | None = None
    current_zone_state = "OFF"
    transition_enabled: bool | None = None
    last_transition_switch_time = 0.0
    last_sent_name = "OFF"
    last_status_time = 0.0

    qi277_status = "-"
    qi276_radius = "-"
    qs573_drift = "-"

    try:
        while True:
            now = time.time()

            readable, _, _ = select.select([psx], [], [], 0.1)

            if psx in readable:
                data = psx.recv(4096)

                if not data:
                    raise ConnectionError("PSX disconnected")

                buffer += data.decode("utf-8", errors="ignore")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()

                    parsed = parse_qs121(line)
                    if parsed:
                        latest_position = parsed
                        continue

                    if line.startswith("Qi277="):
                        qi277_status = line.split("=", 1)[1]
                        continue

                    if line.startswith("Qi276="):
                        qi276_radius = line.split("=", 1)[1]
                        continue

                    if line.startswith("Qs573="):
                        qs573_drift = line.split("=", 1)[1]
                        continue

            active_zone = None
            active_distance_nm = None
            overlapping_zones = []
            wanted_enabled = False
            zone_state = "OFF"

            if latest_position:
                active_zone, active_distance_nm, zone_state, overlapping_zones = find_zone_candidate(
                    latest_position,
                    zones,
                    transition_band_percent,
                )

                wanted_name = active_zone.name if active_zone else "OFF"

                if zone_state == "ACTIVE":
                    wanted_enabled = True
                    transition_enabled = None

                elif zone_state == "TRANSITION" and active_zone:
                    if (
                        transition_enabled is None
                        or wanted_name != current_zone_name
                        or now - last_transition_switch_time >= transition_min_seconds
                    ):
                        transition_enabled = bool(random.getrandbits(1))
                        last_transition_switch_time = now

                    wanted_enabled = transition_enabled

                else:
                    wanted_enabled = False
                    transition_enabled = None

                if wanted_name != current_zone_name or wanted_enabled != current_enabled:
                    if active_zone:
                        qs572 = set_qs572_enabled(active_zone.qs572, wanted_enabled)
                        psx_send(psx, f"Qs572={qs572}")
                        state_text = "ON" if wanted_enabled else "OFF"
                        last_sent_name = f"{active_zone.name} {state_text}"
                    else:
                        psx_send(psx, f"Qs572={OFF_QS572}")
                        last_sent_name = "OFF"

                    current_zone_name = wanted_name
                    current_enabled = wanted_enabled
                    current_zone_state = zone_state

                current_zone_state = zone_state

            if now - last_status_time >= 1.0:
                print_status(
                    psx_host,
                    psx_port,
                    zones,
                    latest_position,
                    active_zone,
                    active_distance_nm,
                    last_sent_name,
                    current_zone_state,
                    transition_enabled,
                    transition_band_percent,
                    transition_min_seconds,
                    qi277_status,
                    qi276_radius,
                    qs573_drift,
                    args.debug,
                    overlapping_zones,
                )
                last_status_time = now

    except KeyboardInterrupt:
        print("\nStopping...")

    except ConnectionError as exc:
        print(f"\n{exc}")

    finally:
        try:
            psx_send(psx, "Qs572=" + OFF_QS572)
            psx_send(psx, "exit")
            time.sleep(0.2)
        except Exception:
            pass

        try:
            psx.close()
        except Exception:
            pass

        print("Connection closed")


if __name__ == "__main__":
    main()
