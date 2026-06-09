# PSX GPS Interference

Automatic GPS interference zone manager for Aerowinx PSX.

This utility uses the GPS Jamming & Spoofing functionality introduced in Aerowinx PSX and automatically activates predefined interference scenarios based on the aircraft's geographical position.

The application continuously monitors the aircraft position and loads the appropriate PSX GPS interference configuration whenever the aircraft enters a configured zone.

All GPS jamming, spoofing, drift calculations, transition behaviour and avionics effects are simulated entirely by Aerowinx PSX. This utility simply automates the activation and deactivation of PSX interference scenarios.

## Features

* Uses the native Aerowinx PSX GPS Jamming & Spoofing simulation
* Automatic zone-based activation
* Supports jamming, spoofing and mixed PSX scenarios
* Unlimited user-defined interference zones
* Overlapping zone management
* Intermittent transition areas near zone boundaries
* Optional debug mode
* Lightweight standalone Python application

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
