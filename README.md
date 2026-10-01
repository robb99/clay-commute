# clay-commute 🚗

Check commute times and traffic conditions from your home to configurable destinations.

## Features

- **Free API**: Uses OSRM (Open Source Routing Machine) - no API key required
- **Multiple destinations**: Configure as many destinations as you need
- **Traffic estimates**: Simple time-of-day based traffic heuristics
- **JSON output**: Script-friendly output for automation
- **Standalone**: No Home Assistant or other local services required

## Installation

```bash
# Clone or copy to your preferred location
cd projects/clay-commute
```

## Configuration

Edit `config.yaml` to set your home location and destinations:

```yaml
home:
  name: "Home"
  lat: 38.2097   # Your home latitude
  lon: -85.2172  # Your home longitude

destinations:
  work:
    name: "Work"
    lat: 38.1989
    lon: -85.3245
    address: "Downtown Louisville"
  
  school:
    name: "Kid's School"
    lat: 38.1856
    lon: -85.3890
    address: "Louisville"

default_destination: work
```

### Getting Coordinates

- Use Google Maps: Right-click a location → click the coordinates
- Use what3words for precise location
- Or use your Home Assistant coordinates from `person.robb_matherly`

## Usage

### List all destinations
```bash
python3 clay_commute.py list
```

Output:
```
Configured destinations:
----------------------------------------
  work: Work (default)
       Downtown Louisville
  school: Silas's School
       Louisville
  iris_school: Iris's School
       Shelbyville
  walmart: Walmart
       Shelbyville
```

### Check commute to default destination
```bash
python3 clay_commute.py check
```

Output:
```
🚗 Work
   From: Home
   To: Downtown Louisville
   Base time: 28 min
   Distance: 14.2 km
   With traffic: 36 min (moderate)
   Traffic factor: 1.3x
```

### Check commute to specific destination
```bash
python3 clay_commute.py check school
```

### Check all destinations
```bash
python3 clay_commute.py all
```

Output:
```
🚗 All Commutes
==================================================
  Walmart: 8 min ⚠️
    Base: 7 min | 5.4 km
  Work: 36 min 🚨
    Base: 28 min | 14.2 km
  Iris's School: 12 min
    Base: 10 min | 3.8 km
  Silas's School: 22 min 🚨
    Base: 17 min | 11.6 km
```

### JSON output (for scripting)
```bash
python3 clay_commute.py check work --json
```

```bash
python3 clay_commute.py all --json
```

## Traffic Estimation

This tool uses a simple time-of-day heuristic for traffic:
- **Morning (7-9am)**: +30-50% travel time
- **Evening (4-6pm)**: +40-60% travel time  
- **Midday (10am-3pm)**: +10% travel time
- **Off-peak**: Base time

*Note: Real-time traffic data requires paid APIs like Google Maps or TomTom.*

## Requirements

- Python 3.7+
- No external dependencies (uses stdlib only!)
- Internet connection for routing API

## Tech Stack

- **Routing**: [OSRM](https://project-osrm.org) (free, no API key)
- **Language**: Python 3

## License

MIT
