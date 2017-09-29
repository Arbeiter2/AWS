from webob import Request, Response
from router import Router
import aws_flights

try:
    unicode = unicode
except NameError:
    # 'unicode' is undefined, must be Python 3
    str = str
    unicode = str
    bytes = bytes
    basestring = (str,bytes)
else:
    # 'unicode' exists, must be Python 2
    str = str
    unicode = unicode
    bytes = str
    basestring = basestring

main = Router()
main.add_route([
# GET, POST - collection
'/games/@game_id:\d+@/flights', 
'/games/@game_id:\d+@/flights/basic', 
# GET, DELETE - flight_number
'/games/@game_id:\d+@/flights/@flight_number:MTX|([A-Z]{2}|[A-Z]\d|\d[A-Z])\d+([;,]([A-Z]{2}|[A-Z]\d|\d[A-Z])\d+)*@',
'/games/@game_id:\d+@/flights/@flight_number:MTX|([A-Z]{2}|[A-Z]\d|\d[A-Z])\d+([;,]([A-Z]{2}|[A-Z]\d|\d[A-Z])\d+)*@/basic',
# GET, DELETE - flight_id
'/games/@game_id:\d+@/flights/@flight_id:\d+([;,]\d+)*@', 
# GET, DELETE - base airport
# airport IATA code
'/games/@game_id:\d+@/flights/@base_airport_iata:[A-Z]{3}@',
'/games/@game_id:\d+@/flights/@base_airport_iata:[A-Z]{3}@/basic',
'/games/@game_id:\d+@/flights/@base_airport_iata:[A-Z]{3}@/@fleet_type_id:\d+([;,]\d+)*@',

# airport ICAO code
'/games/@game_id:\d+@/flights/@base_airport_icao:[A-Z]{4}@',
'/games/@game_id:\d+@/flights/@base_airport_icao:[A-Z]{4}@/basic',# baae airport and fleet_type_id
'/games/@game_id:\d+@/flights/@base_airport_icao:[A-Z]{4}@/@fleet_type_id:\d+([;,]\d+)*@',

# base airport and fleet_type_id
# airport IATA code
'/games/@game_id:\d+@/flights/@base_airport_iata:[A-Z]{3}@/@dest_airport_iata:[A-Z]{3}([;,][A-Z]{3})*@',
# airport ICAO code
'/games/@game_id:\d+@/flights/@base_airport_icao:[A-Z]{4}@/@dest_airport_icao:[A-Z]{4}([;,][A-Z]{3})*@',
           ],
               controller=aws_flights.FlightController)


# req1 = Request.blank('/games/155/flights/515866')
# req1.method = 'DELETE'
# resp1 = req1.get_response(main)
# print(resp1)
    
#for path in ['/games/155/flights/GRX', '/games/155/flights/AV001', '/games/155/flights/515866', '/games/166/flights/LHR/32' ]:
#   req2 = Request.blank(path)
#   resp2 = req2.get_response(main)
#   print(resp2)

#uri = '/games/190/flights/DFW/ORD'
uri = '/games/206/flights/OKBK/OMDB'
req1 = Request.blank(uri)
req1.method = 'GET'
resp1 = req1.get_response(main)
print(resp1)

