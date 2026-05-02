# Fuel Route API — Remote Backend Django Assignment

A Django REST API that calculates the optimal fuel stops between two US locations, minimizing fuel costs based on state-level gas prices.

---

## Features

- Geocode any US city/address to coordinates
- Calculate driving route via OpenRouteService (free API)
- Suggest optimal fuel stops every ~400 miles (vehicle max range: 500 miles)
- Choose cheapest fuel stops based on state gas prices
- Return total fuel cost (vehicle: 10 MPG)
- Return encoded map polyline for frontend rendering

---

## Setup

### 1. Get Free ORS API Key

Sign up at: https://openrouteservice.org/dev/#/signup  
Free tier: 2,000 requests/day — more than enough.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set API Key

**Option A — Environment variable (recommended):**
```bash
export ORS_API_KEY=your_key_here
python manage.py runserver
```

**Option B — Edit settings.py directly:**
```python
ORS_API_KEY = 'your_key_here'
```

### 4. Run Server

```bash
python manage.py migrate
python manage.py runserver
```

---

## API Usage

### Endpoint

```
POST /api/route/
Content-Type: application/json
```

### Request Body

```json
{
    "start": "New York, NY",
    "end": "Los Angeles, CA"
}
```

### Example Response

```json
{
    "start": {
        "input": "New York, NY",
        "resolved": "New York, New York, United States",
        "latitude": 40.71427,
        "longitude": -74.00597
    },
    "end": {
        "input": "Los Angeles, CA",
        "resolved": "Los Angeles, California, United States",
        "latitude": 34.05223,
        "longitude": -118.24368
    },
    "route_summary": {
        "total_distance_miles": 2791.4,
        "estimated_duration": "39h 12m",
        "vehicle_range_miles": 500,
        "vehicle_mpg": 10
    },
    "fuel_stops": [
        {
            "stop_number": 1,
            "mile_marker": 400.0,
            "latitude": 39.96118,
            "longitude": -82.99879,
            "state": "Ohio",
            "state_code": "OH",
            "fuel_price_per_gallon": 3.30,
            "gallons_needed": 40.0,
            "fuel_cost_usd": 132.0
        },
        {
            "stop_number": 2,
            "mile_marker": 800.0,
            "latitude": 37.33939,
            "longitude": -89.13878,
            "state": "Illinois",
            "state_code": "IL",
            "fuel_price_per_gallon": 3.70,
            "gallons_needed": 40.0,
            "fuel_cost_usd": 148.0
        }
    ],
    "cost_summary": {
        "total_fuel_stops": 6,
        "total_gallons_needed": 279.14,
        "total_fuel_cost_usd": 958.72
    },
    "map_polyline": "encoded_string_for_leaflet_or_google_maps"
}
```

### Test with curl

```bash
curl -X POST http://localhost:8000/api/route/ \
  -H "Content-Type: application/json" \
  -d '{"start": "Chicago, IL", "end": "Houston, TX"}'
```

### Test with Postman

1. New Request → POST
2. URL: `http://localhost:8000/api/route/`
3. Body → raw → JSON
4. Paste: `{"start": "Seattle, WA", "end": "Miami, FL"}`
5. Send

---

## Project Structure

```
fuel_route_api/
├── manage.py
├── requirements.txt
├── README.md
├── fuel_route/
│   ├── __init__.py
│   ├── settings.py       # Django settings + ORS_API_KEY
│   ├── urls.py           # Root URL config
│   └── wsgi.py
└── api/
    ├── __init__.py
    ├── fuel_prices.csv   # US state avg gas prices
    ├── services.py       # Core logic: geocoding, routing, fuel stops
    ├── serializers.py    # Input validation
    ├── views.py          # API view
    └── urls.py           # API routes
```

---

## API Calls Made

This API makes at most **3 external calls** per request:
1. `GET /geocode/search` — geocode start location
2. `GET /geocode/search` — geocode end location  
3. `POST /v2/directions/driving-car` — get full route

All via OpenRouteService free tier.

---

## Error Handling

| Status | Meaning |
|--------|---------|
| 400 | Invalid input (empty fields, same start/end, unrecognized location) |
| 401/503 | Invalid or missing ORS API key |
| 429 | ORS rate limit exceeded |
| 502 | ORS API returned an error |
| 504 | ORS API timed out |
| 500 | Unexpected server error |
