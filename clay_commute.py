#!/usr/bin/env python3
"""
clay-commute - Check commute times and traffic conditions

Usage:
    python3 clay_commute.py list              # Show configured destinations
    python3 clay_commute.py check             # Check commute to default destination
    python3 clay_commute.py check "name"      # Check specific destination
    python3 clay_commute.py all               # Check all destinations
    python3 clay_commute.py leave-by "name" "2026-10-23T07:45"  # Latest departure to arrive by a time
    python3 clay_commute.py --json            # JSON output (combine with above)
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

# Resolve symlinks so the tool finds config.yaml next to the real script,
# not next to the symlink in tools/ (which would be a different file).
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"

# Default configuration (Shelbyville, KY area)
DEFAULT_CONFIG = {
    "home": {
        "lat": 38.2097,
        "lon": -85.2172,
        "name": "Home"
    },
    "destinations": {
        "work": {
            "name": "Work",
            "lat": 38.1989,
            "lon": -85.3245,
            "address": "Downtown Louisville"
        },
        "school": {
            "name": "Silas's School",
            "lat": 38.1856,
            "lon": -85.3890,
            "address": "Louisville"
        },
        "iris_school": {
            "name": "Iris's School",
            "lat": 38.2120,
            "lon": -85.2015,
            "address": "Shelbyville"
        },
        "walmart": {
            "name": "Walmart",
            "lat": 38.2156,
            "lon": -85.2689,
            "address": " Shelbyville"
        },
        "georgetown": {
            "name": "Ferguson Georgetown",
            "lat": 38.2055,
            "lon": -84.5597,
            "address": "Downtown Georgetown, KY"
        }
    },
    "default_destination": "work"
}


def load_config():
    """Load configuration from config.yaml or use defaults."""
    if CONFIG_PATH.exists():
        try:
            import yaml
            with open(CONFIG_PATH, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except ImportError:
            print("Warning: pyyaml not installed, using default config", file=sys.stderr)
    
    return DEFAULT_CONFIG


def get_route_time(lat1, lon1, lat2, lon2):
    """
    Get driving time using OpenRouteService free API.
    Returns (duration_minutes, distance_km, error) tuple.
    """
    import ssl
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
    
    try:
        # Create unverified SSL context
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers={'User-Agent': 'clay-commute/1.0'})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        if data.get('code') == 'Ok' and data.get('routes'):
            route = data['routes'][0]
            duration_seconds = route['duration']
            distance_meters = route['distance']
            return (
                round(duration_seconds / 60, 1),
                round(distance_meters / 1000, 1),
                None
            )
        else:
            return None, None, data.get('message', 'Unknown error')
            
    except urllib.error.URLError as e:
        return None, None, str(e)
    except json.JSONDecodeError as e:
        return None, None, f"JSON error: {e}"
    except Exception as e:
        return None, None, str(e)


def get_traffic_estimate(duration_minutes, at_hour=None, conservative=False):
    """
    Estimate traffic condition based on time of day.
    This is a simple heuristic - real traffic data requires paid APIs.

    at_hour: the hour of day the trip will actually happen (0-23). Defaults to
    the current hour. Passing the departure hour matters: checking a commute
    at 6 AM for a 7:45 AM arrival should not assume off-peak conditions.

    conservative: use the worst case of the traffic band instead of a random
    draw. Departure deadlines must be deterministic -- a leave-by time that
    changes between runs is worse than no leave-by time at all.
    """
    from datetime import datetime
    import random
    
    now = datetime.now()
    hour = now.hour if at_hour is None else int(at_hour)
    
    # Typical commute hours
    if 7 <= hour <= 9:
        # Morning rush - typically 1.2-1.5x longer
        factor = 1.5 if conservative else 1.3 + (random.random() * 0.2)
    elif 16 <= hour <= 18:
        # Evening rush - typically 1.2-1.6x longer
        factor = 1.6 if conservative else 1.4 + (random.random() * 0.2)
    elif 10 <= hour <= 15:
        # Midday - slightly more traffic
        factor = 1.1
    else:
        # Off-peak - base time
        factor = 1.0
    
    estimated = round(duration_minutes * factor, 1)
    return estimated, factor


def format_duration(minutes):
    """Format minutes into human-readable string."""
    if minutes < 60:
        return f"{minutes} min"
    else:
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        if mins == 0:
            return f"{hours}h"
        return f"{hours}h {mins}m"


def list_destinations(config):
    """List all configured destinations."""
    destinations = config.get('destinations', {})
    default = config.get('default_destination', '')
    
    print("Configured destinations:")
    print("-" * 40)
    for key, dest in destinations.items():
        marker = " (default)" if key == default else ""
        print(f"  {key}: {dest.get('name', key)}{marker}")
        if 'address' in dest:
            print(f"       {dest['address']}")


def check_commute(config, destination_key=None, json_output=False):
    """Check commute time to a destination."""
    destinations = config.get('destinations', {})
    home = config.get('home', {})
    
    if destination_key is None:
        destination_key = config.get('default_destination', '')
    
    if destination_key not in destinations:
        print(f"Error: Unknown destination '{destination_key}'", file=sys.stderr)
        print(f"Available: {', '.join(destinations.keys())}", file=sys.stderr)
        sys.exit(1)
    
    dest = destinations[destination_key]
    home_lat = home.get('lat')
    home_lon = home.get('lon')
    dest_lat = dest.get('lat')
    dest_lon = dest.get('lon')
    
    duration, distance, error = get_route_time(home_lat, home_lon, dest_lat, dest_lon)
    
    if error:
        if json_output:
            result = {
                "success": False,
                "error": error,
                "destination": destination_key,
                "destination_name": dest.get('name'),
                "home": home.get('name')
            }
            print(json.dumps(result, indent=2))
        else:
            print(f"Error getting route: {error}", file=sys.stderr)
        sys.exit(1)
    
    traffic_time, factor = get_traffic_estimate(duration)
    
    result = {
        "success": True,
        "destination": destination_key,
        "destination_name": dest.get('name'),
        "destination_address": dest.get('address', ''),
        "home": home.get('name'),
        "base_duration_minutes": duration,
        "distance_km": distance,
        "estimated_duration_minutes": traffic_time,
        "traffic_factor": round(factor, 2),
        "traffic_level": "heavy" if factor > 1.3 else "moderate" if factor > 1.1 else "light"
    }
    
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"🚗 {dest.get('name')}")
        print(f"   From: {home.get('name')}")
        if dest.get('address'):
            print(f"   To: {dest['address']}")
        print(f"   Base time: {format_duration(duration)}")
        print(f"   Distance: {distance} km")
        if traffic_time != duration:
            print(f"   With traffic: {format_duration(traffic_time)} ({result['traffic_level']})")
        print(f"   Traffic factor: {result['traffic_factor']}x")


def check_all_commutes(config, json_output=False):
    """Check commute times to all destinations."""
    destinations = config.get('destinations', {})
    results = []
    
    for key, dest in destinations.items():
        home = config.get('home', {})
        duration, distance, error = get_route_time(
            home.get('lat'), home.get('lon'),
            dest.get('lat'), dest.get('lon')
        )
        
        if error:
            results.append({
                "destination": key,
                "destination_name": dest.get('name'),
                "success": False,
                "error": error
            })
            continue
        
        traffic_time, factor = get_traffic_estimate(duration)
        
        results.append({
            "success": True,
            "destination": key,
            "destination_name": dest.get('name'),
            "destination_address": dest.get('address', ''),
            "base_duration_minutes": duration,
            "distance_km": distance,
            "estimated_duration_minutes": traffic_time,
            "traffic_factor": round(factor, 2),
            "traffic_level": "heavy" if factor > 1.3 else "moderate" if factor > 1.1 else "light"
        })
    
    if json_output:
        print(json.dumps(results, indent=2))
    else:
        print("🚗 All Commutes")
        print("=" * 50)
        
        # Sort by estimated time
        results_sorted = sorted(
            [r for r in results if r.get('success')], 
            key=lambda x: x.get('estimated_duration_minutes', 999)
        )
        
        for r in results_sorted:
            traffic_indicator = ""
            if r.get('traffic_level') == 'heavy':
                traffic_indicator = " 🚨"
            elif r.get('traffic_level') == 'moderate':
                traffic_indicator = " ⚠️"
            
            print(f"  {r['destination_name']}: {format_duration(r['estimated_duration_minutes'])}{traffic_indicator}")
            print(f"    Base: {format_duration(r['base_duration_minutes'])} | {r['distance_km']} km")


def resolve_origin(config, origin_key):
    """
    Resolve an origin for a trip. Accepts:
      - 'home'  -> the configured home coordinates
      - a destination key -> that destination's coordinates
      - 'current' -> live position from Home Assistant (device_tracker.robbs_iphone)
    Returns (lat, lon, label, error).
    """
    destinations = config.get('destinations', {})
    home = config.get('home', {})

    if origin_key in (None, 'home'):
        return home.get('lat'), home.get('lon'), home.get('name', 'Home'), None

    if origin_key == 'current':
        try:
            import ssl
            import urllib.request as ur
            secret = Path(__file__).resolve().parents[2] / ".secrets" / "ha-token"
            if not secret.exists():
                return None, None, None, "No HA token at .secrets/ha-token"
            token = secret.read_text().strip()
            req = ur.Request(
                "http://192.168.1.135:8123/api/states/device_tracker.robbs_iphone",
                headers={'Authorization': 'Bearer ' + token})
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with ur.urlopen(req, timeout=10, context=ctx) as resp:
                state = json.loads(resp.read().decode('utf-8'))
            attrs = state.get('attributes', {})
            return attrs.get('latitude'), attrs.get('longitude'), "current location", None
        except Exception as e:
            return None, None, None, f"Could not read current position: {e}"

    if origin_key in destinations:
        d = destinations[origin_key]
        return d.get('lat'), d.get('lon'), d.get('name', origin_key), None

    return None, None, None, (
        f"Unknown origin '{origin_key}'. Use 'home', 'current', or one of: "
        f"{', '.join(destinations.keys())}")


def leave_by(config, destination_key, arrive_by_iso, json_output=False, origin_key='home'):
    """Work out the latest departure time to arrive by a given ISO timestamp."""
    from datetime import datetime, timedelta

    destinations = config.get('destinations', {})

    if destination_key not in destinations:
        print(f"Error: Unknown destination '{destination_key}'", file=sys.stderr)
        print(f"Available: {', '.join(destinations.keys())}", file=sys.stderr)
        sys.exit(1)

    o_lat, o_lon, o_label, o_err = resolve_origin(config, origin_key)
    if o_err:
        print(f"Error resolving origin: {o_err}", file=sys.stderr)
        sys.exit(1)

    dest = destinations[destination_key]
    duration, distance, error = get_route_time(
        o_lat, o_lon, dest.get('lat'), dest.get('lon'))

    if error:
        print(f"Error getting route: {error}", file=sys.stderr)
        sys.exit(1)

    arrive_by = datetime.fromisoformat(arrive_by_iso)

    # The trip spans departure -> arrival, so pick the worst traffic factor
    # across the hours it covers rather than just the departure hour.
    best_departure = None
    for minutes_earlier in range(0, 180):
        depart = arrive_by - timedelta(minutes=minutes_earlier)
        # Base case: is the base drive time enough on its own?
        if minutes_earlier == 0:
            # Binary-search-ish: find the largest departure offset that fits.
            pass
        hours = {depart.hour, (depart + timedelta(minutes=duration)).hour}
        factor = max(get_traffic_estimate(duration, h, conservative=True)[1] for h in hours)
        trip_minutes = duration * factor
        if trip_minutes <= minutes_earlier:
            best_departure = (depart, factor, trip_minutes)
            break

    if best_departure is None:
        # Even a departure 3h early is tight -- report the earliest candidate.
        depart = arrive_by - timedelta(minutes=180)
        factor = get_traffic_estimate(duration, depart.hour, conservative=True)[1]
        best_departure = (depart, factor, duration * factor)

    depart, factor, trip_minutes = best_departure
    result = {
        "success": True,
        "origin": origin_key,
        "origin_name": o_label,
        "destination": destination_key,
        "destination_name": dest.get('name'),
        "destination_address": dest.get('address', ''),
        "arrive_by": arrive_by.isoformat(),
        "leave_by": depart.isoformat(),
        "base_duration_minutes": duration,
        "distance_km": distance,
        "traffic_factor": round(factor, 2),
        "estimated_duration_minutes": round(trip_minutes, 1),
        "buffer_minutes": round((arrive_by - depart).total_seconds() / 60 - trip_minutes, 1),
    }

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"🚗 {o_label} → {dest.get('name')} ({dest.get('address','')})")
        print(f"   Arrive by:  {arrive_by.strftime('%a %b %-d, %-I:%M %p')}")
        print(f"   Leave by:   {depart.strftime('%a %b %-d, %-I:%M %p')}")
        print(f"   Drive time: {format_duration(trip_minutes)} (base {format_duration(duration)}, {result['traffic_factor']}x traffic)")
        print(f"   Distance:   {distance} km")
        print(f"   Buffer:     {result['buffer_minutes']:.0f} min spare")


def main():
    parser = argparse.ArgumentParser(
        description='clay-commute - Check commute times and traffic conditions'
    )
    parser.add_argument(
        'command',
        nargs='?',
        choices=['list', 'check', 'all', 'leave-by'],
        default='check',
        help='Command to run'
    )
    parser.add_argument(
        'destination',
        nargs='?',
        help='Destination key (for check command)'
    )
    parser.add_argument(
        'arrive_by',
        nargs='?',
        help='Arrival time in ISO format, e.g. 2026-10-23T07:45 (for leave-by)'
    )
    parser.add_argument(
        '--from', '-f',
        dest='origin',
        default='home',
        help="Origin for leave-by: 'home' (default), 'current' (live HA position), "
             "or a destination key like 'ferguson'"
    )
    parser.add_argument(
        '--json', '-j',
        action='store_true',
        help='Output as JSON'
    )
    
    args = parser.parse_args()
    config = load_config()
    
    if args.command == 'list':
        list_destinations(config)
    elif args.command == 'check':
        check_commute(config, args.destination, args.json)
    elif args.command == 'all':
        check_all_commutes(config, args.json)
    elif args.command == 'leave-by':
        if not args.destination or not args.arrive_by:
            print("Error: leave-by needs a destination and an arrival time", file=sys.stderr)
            print('Usage: clay_commute.py leave-by "work" "2026-10-23T07:45"', file=sys.stderr)
            sys.exit(1)
        leave_by(config, args.destination, args.arrive_by, args.json, args.origin)


if __name__ == '__main__':
    main()
