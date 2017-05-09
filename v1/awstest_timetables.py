from webob import Request, Response
from router import Router
import aws_timetables

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
    '/games/@game_id:\d+@/timetables', # GET, POST
    '/games/@game_id:\d+@/timetables/search/flights'
    '/@flight_number:([A-Z]{2}|[A-Z]\d|\d[A-Z])\d+([;,]([A-Z]{2}|[A-Z]\d|\d[A-Z])\d+)*@', # GET
    '/games/@game_id:\d+@/timetables/search/airports'
    '/@dest_airport_iata:([A-Z]{3}([,;][A-Z]{3})*)@', # GET
    '/games/@game_id:\d+@/timetables/conflicts/@base_airport_iata:[A-Z]{3}@', # GET
    '/games/@game_id:\d+@/timetables/conflicts/@timetable_id:\d+(;\d+)*@', # GET
    '/games/@game_id:\d+@/timetables/@mode:(all|flights)@', # GET
    '/games/@game_id:\d+@/timetables/@timetable_id:\d+@', # DELETE, GET, POST, PUT
    '/games/@game_id:\d+@/timetables/@timetable_id:\d+(;\d+)*@', # DELETE, GET
    '/games/@game_id:\d+@/timetables/@base_airport_iata:[A-Z]{3}@', # DELETE, GET
    '/games/@game_id:\d+@/timetables/@base_airport_iata:[A-Z]{3}@/@fleet_type_id:\d+@', # DELETE, GET

    ],
    controller=aws_timetables.TimetableController)

               
   
req1 = Request.blank("/games/206/timetables/search/airports/DOH")
#req1.accept = "application/json; q=0.5, text/html;q=1"
#req1.accept = "text/html;q=1"
req1.method = 'GET'
#resp1 = req1.get_response(main)
#print(resp1)               

#req1 = Request.blank("/games/190/timetables/flights")
#req1.method = 'GET'
resp1 = req1.get_response(main)
print(resp1)
