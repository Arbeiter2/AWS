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
'/games/@game_id:\d+@/flights/@base_airport_iata:[A-Z]{3}@',
'/games/@game_id:\d+@/flights/@base_airport_iata:[A-Z]{3}@/basic',
# baae airport and fleet_type_id
'/games/@game_id:\d+@/flights/@base_airport_iata:[A-Z]{3}@/@fleet_type_id:\d+([;,]\d+)*@',
 # baae airport and fleet_type_id
'/games/@game_id:\d+@/flights/@base_airport_iata:[A-Z]{3}@/@dest_airport_iata:[A-Z]{3}([;,][A-Z]{3})*@',
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

uri = '/games/190/flights/DFW/ORD'
#uri = '/games/190/flights/QV103'
req1 = Request.blank(uri)
req1.method = 'GET'
resp1 = req1.get_response(main)
print(resp1)

##uri = '/games/190/flights'
##req1 = Request.blank(uri)
##req1.method = 'POST'
##req1.body = b'''{"base_airport_iata":"DFW","dest_airport_iata":"LGA","game_name":"Beginner\'s World #2","game_id":"190","number":"001","flight_number":"QV001","fleet_type":"Boeing 737-300/400/500","fleet_type_id":"23","blocked_seats":"0","days_flown":"1------","distance_nm":"1204","outbound_dep_time":"12:00","outbound_arr_time":"16:40","outbound_length":"03:40","inbound_dep_time":"17:50","inbound_arr_time":"20:50","inbound_length":"04:00","turnaround_length":"01:10","min_turnaround":"00:40","turnaround_mins":"70","min_turnaround_mins":"40","flight_id":"14870"}'''
##resp1 = req1.get_response(main)
##print(resp1)
