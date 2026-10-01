#!/usr/bin/env python3
"""
clay-commute - Check commute times and traffic conditions

Usage:
    python3 clay_commute.py list              # Show configured destinations
    python3 clay_commute.py check             # Check commute to default destination
    python3 clay_commute.py check "name"      # Check specific destination
    python3 clay_commute.py all               # Check all destinations
    python3 clay_commute.py --json            # JSON output (combine with above)
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.yaml"

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


def get_traffic_estimate(duration_minutes):
    """
    Estimate traffic condition based on time of day.
    This is a simple heuristic - real traffic data requires paid APIs.
    """
    from datetime import datetime
    import random
    
    now = datetime.now()
    hour = now.hour
    
    # Typical commute hours
    if 7 <= hour <= 9:
        # Morning rush - typically 1.2-1.5x longer
        factor = 1.3 + (random.random() * 0.2)
    elif 16 <= hour <= 18:
        # Evening rush - typically 1.2-1.6x longer
        factor = 1.4 + (random.random() * 0.2)
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


def main():
    parser = argparse.ArgumentParser(
        description='clay-commute - Check commute times and traffic conditions'
    )
    parser.add_argument(
        'command',
        nargs='?',
        choices=['list', 'check', 'all'],
        default='check',
        help='Command to run'
    )
    parser.add_argument(
        'destination',
        nargs='?',
        help='Destination key (for check command)'
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


if __name__ == '__main__':
    main()
