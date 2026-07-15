# django_project/osrm_service.py
import os
import requests
from django.conf import settings

# Try importing the bindings. If not installed/compiled, we fallback to requests to public OSRM API
try:
    import osrm
    OSRM_PATH = getattr(settings, 'OSRM_DATA_PATH', 'path/to/data.osrm')
    if os.path.exists(OSRM_PATH):
        OSRM_ENGINE = osrm.OSRM(OSRM_PATH, algorithm="CH")
    else:
        OSRM_ENGINE = None
except ImportError:
    OSRM_ENGINE = None

def get_route(start_lon, start_lat, end_lon, end_lat):
    """
    Returns (geojson_geometry, duration_seconds, distance_meters)
    """
    # 1. Try local binary engine first
    if OSRM_ENGINE:
        try:
            params = osrm.RouteParameters(
                coordinates=[(float(start_lon), float(start_lat)), (float(end_lon), float(end_lat))],
                steps=False,
                geometries="geojson",
                overview="full"
            )
            result = OSRM_ENGINE.Route(params)
            route = result["routes"][0]
            return route["geometry"], route["duration"], route["distance"]
        except Exception as e:
            print(f"Local OSRM Error: {e}")

    # 2. Fallback to OSRM Public Web API (Great for development!)
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("routes"):
                route = data["routes"][0]
                return route["geometry"], route["duration"], route["distance"]
    except Exception as e:
        print(f"OSRM API Fallback Error: {e}")
        
    # Return a straight line fallback if both fail
    straight_line_geom = {
        "type": "LineString",
        "coordinates": [[float(start_lon), float(start_lat)], [float(end_lon), float(end_lat)]]
    }
    return straight_line_geom, 300.0, 1000.0