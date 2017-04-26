from router import Router
import aws_games
import aws_airports
import aws_timetables
import aws_flights
import aws_fleets

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


def application(environ, start_response):
    main = Router()
    # games
    main.add_route([
    # DELETE, GET, POST - games
    '/games', 
    # GET - games and bases                      
    '/games',
    '/games/@bases:(bases)@',
    '/games/@game_id:\d+([;,]\d+)*@',
    '/games/@game_id:\d+@/@mode:(fleets|bases|airports)@',
    ],
    controller=aws_games.GameController)

    # fleets
    main.add_route([
    '/fleets/@fleet_type_id:\d+([;,]\d+)*@', # GET
    '/fleets', # GET
    ],
    controller=aws_fleets.FleetController)
    
    # airports and curfews
    main.add_route([
    # GET
    '/airports/@iata_code:[A-Z]{3}@',
    '/airports/@iata_code:[A-Z]{3}([;,][A-Z]{3})*@',
    # GET
    '/airports/@icao_code:[A-Z]{4}@',
    '/airports/@icao_code:[A-Z]{4}([;,][A-Z]{4})*@',
    # GET, POST, PUT, DELETE
    '/airports/@iata_code:[A-Z]{3}@/curfew',
    # GET, POST, PUT, DELETE
    '/airports/@icao_code:[A-Z]{4}@/curfew',
    # POST, PUT
    '/airports/@iata_code:[A-Z]{3}@/curfew/@start:\d{2}:\d{2}@/@finish:\d{2}:\d{2}@',  # PUT
    # POST, PUT
    '/airports/@icao_code:[A-Z]{4}@/curfew/@start:\d{2}:\d{2}@/@finish:\d{2}:\d{2}@',  # PUT

    ],
    controller=aws_airports.AirportController)
               
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

    # timetables
    main.add_route([ 
    # GET, POST
    '/games/@game_id:\d+@/timetables',
    '/games/@game_id:\d+@/timetables/@mode:(all|flights)@',
    # DELETE, GET, POST, PUT
    '/games/@game_id:\d+@/timetables/@timetable_id:\d+@',
    # DELETE, GET
    '/games/@game_id:\d+@/timetables/@timetable_id:\d+([;,]\d+)*@',
    # GET
    '/games/@game_id:\d+@/timetables/@base_airport_iata:[A-Z]{3}@',
    # GET
    '/games/@game_id:\d+@/timetables/@base_airport_iata:[A-Z]{3}@/@fleet_type_id:\d+@',
    
    # GET
    '/games/@game_id:\d+@/timetables/search/flights/@flight_number:'
    '([A-Z]{2}|[A-Z]\d|\d[A-Z])\d+([;,]([A-Z]{2}|[A-Z]\d|\d[A-Z])\d+)*@', # GET
     
    # GET
    '/games/@game_id:\d+@/timetables/conflicts/@base_airport_iata:[A-Z]{3}@',
    # GET
    '/games/@game_id:\d+@/timetables/conflicts/@timetable_id:\d+(;\d+)*@',
    ],
    controller=aws_timetables.TimetableController)

    return main(environ, start_response)