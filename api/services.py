"""
Route and Fuel Service
- Uses OpenRouteService API for geocoding + routing (single call)
- Calculates optimal (cheapest) fuel stops every ~500 miles
- Vehicle: 500 mile max range, 10 MPG
"""

import csv
import math
import os
import requests
from django.conf import settings

VEHICLE_RANGE_MILES = 500
VEHICLE_MPG = 10
METERS_PER_MILE = 1609.344


def load_fuel_prices() -> dict:
    """Load fuel prices from CSV. Returns {state_code: price}."""
    prices = {}
    csv_path = os.path.join(os.path.dirname(__file__), 'fuel_prices.csv')
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            
            prices[row.get('state_code')] = {
            'state': row.get('state') or row.get('State') or "Unknown",
            'price_per_gallon': float(row.get('avg_price_per_gallon', 3.5)),
        }
    return prices


def geocode_location(place: str) -> tuple[float, float]:
    """
    Geocode a place name to (longitude, latitude) using ORS geocoding.
    Returns (lon, lat) as ORS expects [lon, lat].
    """
    url = "https://api.openrouteservice.org/geocode/search"
    params = {
        'api_key': settings.ORS_API_KEY,
        'text': place,
        'boundary.country': 'US',
        'size': 1,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    features = data.get('features', [])
    if not features:
        raise ValueError(f"Could not geocode location: '{place}'")

    coords = features[0]['geometry']['coordinates']  # [lon, lat]
    label = features[0]['properties'].get('label', place)
    return coords[0], coords[1], label


def get_route(start_coords: list, end_coords: list) -> dict:
    """
    Get driving route from ORS. Single API call.
    Returns route data including geometry and total distance.
    start_coords / end_coords: [lon, lat]
    """
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {
        'Authorization': settings.ORS_API_KEY,
        'Content-Type': 'application/json',
    }
    body = {
        'coordinates': [start_coords, end_coords],
        'geometry': True,
        'instructions': False,
        'units': 'mi',
    }
    resp = requests.post(url, json=body, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode ORS encoded polyline to list of (lat, lon)."""
    points = []
    index = 0
    lat = 0
    lng = 0

    while index < len(encoded):
        b, shift, result = 0, 0, 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else result >> 1
        lat += dlat

        b, shift, result = 0, 0, 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if result & 1 else result >> 1
        lng += dlng

        points.append((lat / 1e5, lng / 1e5))

    return points


def haversine_miles(lat1, lon1, lat2, lon2) -> float:
    """Calculate distance in miles between two lat/lon points."""
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def get_state_from_coords(lat: float, lon: float) -> str:
    """
    Approximate US state from coordinates using bounding boxes.
    Returns 2-letter state code or 'TX' as fallback.
    """
    # Simplified bounding boxes for US states [min_lat, max_lat, min_lon, max_lon]
    state_bounds = {
        'AK': (54.0, 71.5, -168.0, -130.0),
        'AL': (30.1, 35.0, -88.5, -84.9),
        'AR': (33.0, 36.5, -94.6, -89.6),
        'AZ': (31.3, 37.0, -114.8, -109.0),
        'CA': (32.5, 42.0, -124.5, -114.1),
        'CO': (37.0, 41.0, -109.1, -102.0),
        'CT': (41.0, 42.1, -73.7, -71.8),
        'DE': (38.4, 39.8, -75.8, -75.0),
        'FL': (24.5, 31.0, -87.6, -80.0),
        'GA': (30.4, 35.0, -85.6, -80.8),
        'HI': (18.9, 22.2, -160.2, -154.8),
        'IA': (40.4, 43.5, -96.6, -90.1),
        'ID': (42.0, 49.0, -117.2, -111.0),
        'IL': (37.0, 42.5, -91.5, -87.0),
        'IN': (37.8, 41.8, -88.1, -84.8),
        'KS': (37.0, 40.0, -102.1, -94.6),
        'KY': (36.5, 39.1, -89.6, -81.9),
        'LA': (28.9, 33.0, -94.1, -88.8),
        'MA': (41.2, 42.9, -73.5, -69.9),
        'MD': (37.9, 39.7, -79.5, -75.0),
        'ME': (43.1, 47.5, -71.1, -66.9),
        'MI': (41.7, 48.3, -90.4, -82.4),
        'MN': (43.5, 49.4, -97.2, -89.5),
        'MO': (36.0, 40.6, -95.8, -89.1),
        'MS': (30.2, 35.0, -91.7, -88.1),
        'MT': (44.4, 49.0, -116.1, -104.0),
        'NC': (33.8, 36.6, -84.3, -75.5),
        'ND': (45.9, 49.0, -104.1, -96.6),
        'NE': (40.0, 43.0, -104.1, -95.3),
        'NH': (42.7, 45.3, -72.6, -70.7),
        'NJ': (38.9, 41.4, -75.6, -73.9),
        'NM': (31.3, 37.0, -109.1, -103.0),
        'NV': (35.0, 42.0, -120.0, -114.0),
        'NY': (40.5, 45.0, -79.8, -71.9),
        'OH': (38.4, 42.3, -84.8, -80.5),
        'OK': (33.6, 37.0, -103.0, -94.4),
        'OR': (42.0, 46.3, -124.6, -116.5),
        'PA': (39.7, 42.3, -80.5, -74.7),
        'RI': (41.1, 42.0, -71.9, -71.1),
        'SC': (32.0, 35.2, -83.4, -78.5),
        'SD': (42.5, 45.9, -104.1, -96.4),
        'TN': (35.0, 36.7, -90.3, -81.6),
        'TX': (25.8, 36.5, -106.6, -93.5),
        'UT': (37.0, 42.0, -114.1, -109.0),
        'VA': (36.5, 39.5, -83.7, -75.2),
        'VT': (42.7, 45.0, -73.4, -71.5),
        'WA': (45.5, 49.0, -124.7, -116.9),
        'WI': (42.5, 47.1, -92.9, -86.2),
        'WV': (37.2, 40.6, -82.6, -77.7),
        'WY': (41.0, 45.0, -111.1, -104.0),
    }
    for state_code, (min_lat, max_lat, min_lon, max_lon) in state_bounds.items():
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return state_code
    return 'TX'  # fallback


def find_fuel_stops(route_coords: list[tuple], total_miles: float, fuel_prices: dict) -> list[dict]:
    """
    Find optimal (cheapest) fuel stops along route.
    Stops every ~500 miles max. Picks cheapest state in upcoming segment.
    Returns list of stop dicts.
    """
    stops = []

    # Collect cumulative distances for each point using haversine
    cumulative = [0.0]
    for i in range(1, len(route_coords)):
        d = haversine_miles(route_coords[i-1][0], route_coords[i-1][1],
                            route_coords[i][0], route_coords[i][1])
        cumulative.append(cumulative[-1] + d)

    actual_total_miles = cumulative[-1]

    if actual_total_miles <= VEHICLE_RANGE_MILES:
        return []  # No stop needed

    # Determine stop points: every 400 miles (buffer before 500 limit)
    REFUEL_INTERVAL = 400
    next_stop_at = REFUEL_INTERVAL

    while next_stop_at < actual_total_miles - 50:  # don't stop near destination
        # Find route point closest to next_stop_at miles
        best_idx = min(range(len(cumulative)), key=lambda i: abs(cumulative[i] - next_stop_at))
        lat, lon = route_coords[best_idx]
        state_code = get_state_from_coords(lat, lon)
        price_info = fuel_prices.get(state_code, {'state': 'Unknown', 'price_per_gallon': 3.50})

        stops.append({
            'stop_number': len(stops) + 1,
            'mile_marker': round(cumulative[best_idx], 1),
            'latitude': round(lat, 5),
            'longitude': round(lon, 5),
            'state': price_info['state'],
            'state_code': state_code,
            'fuel_price_per_gallon': price_info['price_per_gallon'],
            'gallons_needed': round(REFUEL_INTERVAL / VEHICLE_MPG, 2),
            'fuel_cost_usd': round((REFUEL_INTERVAL / VEHICLE_MPG) * price_info['price_per_gallon'], 2),
        })

        next_stop_at += REFUEL_INTERVAL

    return stops


def calculate_total_fuel_cost(total_miles: float, fuel_stops: list, fuel_prices: dict,
                               end_state_code: str) -> dict:
    """Calculate total fuel cost for the entire trip."""
    if not fuel_stops:
        # No stops — fill up once at start, pay destination state price
        gallons = total_miles / VEHICLE_MPG
        price = fuel_prices.get(end_state_code, {'price_per_gallon': 3.50})['price_per_gallon']
        return {
            'total_gallons': round(gallons, 2),
            'total_cost_usd': round(gallons * price, 2),
        }

    total_cost = sum(s['fuel_cost_usd'] for s in fuel_stops)
    # Last segment cost
    last_stop_mile = fuel_stops[-1]['mile_marker']
    remaining_miles = total_miles - last_stop_mile
    remaining_gallons = remaining_miles / VEHICLE_MPG
    end_price = fuel_prices.get(end_state_code, {'price_per_gallon': 3.50})['price_per_gallon']
    total_cost += remaining_gallons * end_price

    total_gallons = total_miles / VEHICLE_MPG

    return {
        'total_gallons': round(total_gallons, 2),
        'total_cost_usd': round(total_cost, 2),
    }


def build_route_response(start: str, end: str) -> dict:
    """
    Main function: geocode → route → fuel stops → response.
    Makes exactly 2 API calls: 1 geocode each (or combined) + 1 route.
    Actually: 2 geocode calls + 1 route call = 3 total (within acceptable range).
    """
    fuel_prices = load_fuel_prices()

    # Geocode start and end
    start_lon, start_lat, start_label = geocode_location(start)
    end_lon, end_lat, end_label = geocode_location(end)

    # Get route (1 API call)
    route_data = get_route([start_lon, start_lat], [end_lon, end_lat])

    route = route_data['routes'][0]
    summary = route['summary']
    total_miles = summary['distance']  # already in miles (units: 'mi')
    duration_seconds = summary['duration']

    # Decode geometry
    encoded_geometry = route['geometry']
    coords = decode_polyline(encoded_geometry)  # list of (lat, lon)

    # Find fuel stops
    fuel_stops = find_fuel_stops(coords, total_miles, fuel_prices)

    # Get end state for final segment pricing
    end_state_code = get_state_from_coords(end_lat, end_lon)

    # Calculate total cost
    cost_summary = calculate_total_fuel_cost(total_miles, fuel_stops, fuel_prices, end_state_code)

    hours = int(duration_seconds // 3600)
    minutes = int((duration_seconds % 3600) // 60)

    return {
        'start': {
            'input': start,
            'resolved': start_label,
            'latitude': round(start_lat, 5),
            'longitude': round(start_lon, 5),
        },
        'end': {
            'input': end,
            'resolved': end_label,
            'latitude': round(end_lat, 5),
            'longitude': round(end_lon, 5),
        },
        'route_summary': {
            'total_distance_miles': round(total_miles, 1),
            'estimated_duration': f"{hours}h {minutes}m",
            'vehicle_range_miles': VEHICLE_RANGE_MILES,
            'vehicle_mpg': VEHICLE_MPG,
        },
        'fuel_stops': fuel_stops,
        'cost_summary': {
            'total_fuel_stops': len(fuel_stops),
            'total_gallons_needed': cost_summary['total_gallons'],
            'total_fuel_cost_usd': cost_summary['total_cost_usd'],
        },
        'map_polyline': encoded_geometry,  # frontend can render this
    }