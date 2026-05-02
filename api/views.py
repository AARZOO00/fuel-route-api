import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import RouteRequestSerializer
from .services import build_route_response


class FuelRouteView(APIView):
    """
    POST /api/route/
    
    Calculate optimal fuel stops between two US locations.
    
    Request body:
        {
            "start": "New York, NY",
            "end": "Los Angeles, CA"
        }
    
    Response:
        {
            "start": { ... },
            "end": { ... },
            "route_summary": { ... },
            "fuel_stops": [ ... ],
            "cost_summary": { ... },
            "map_polyline": "encoded_string"
        }
    """

    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        start = serializer.validated_data['start']
        end = serializer.validated_data['end']

        try:
            result = build_route_response(start, end)
            return Response(result, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                return Response(
                    {'error': 'Invalid ORS API key. Get yours free at https://openrouteservice.org/dev/#/signup'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            elif e.response is not None and e.response.status_code == 429:
                return Response(
                    {'error': 'ORS API rate limit exceeded. Please wait and try again.'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
            return Response(
                {'error': f'Routing API error: {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except requests.exceptions.ConnectionError:
            return Response(
                {'error': 'Could not connect to routing API. Check your internet connection.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except requests.exceptions.Timeout:
            return Response(
                {'error': 'Routing API request timed out. Please try again.'},
                status=status.HTTP_504_GATEWAY_TIMEOUT
            )
        except Exception as e:
            return Response(
                {'error': f'Unexpected error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
