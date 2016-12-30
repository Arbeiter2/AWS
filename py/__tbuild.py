#!/usr/bin/python3

from flights import Airport, Flight, FleetType, FlightCollection, MaintenanceCheckA
from timetables import Timetable, TimetableEntry, TimetableManager
from mysql import connector
from mysql.connector.errors import Error
import sys, getopt
from threading import Timer
from datetime import timedelta
from nptools import str_to_timedelta, str_to_nptime, timedelta_to_hhmm
import pdb

threshold = 0.99
airports = {}
fleet_types = {}
routes = {}
flight_lookup = {}
flightColl = FlightCollection()
ttManager = TimetableManager()
types = {
    'F50' : 37, 
    'B732' : 22, 
    'B733' : 23, 
    'B736' : 24, 
    'A340' : 8, 
    'B757' : 28, 
    'B767' : 29, 
    'B777' : 30,
    'DH8D' : 106,
    'A320' : 7,
    }      
timetableCounts = {}

    
class ThreadController:
    threadStop = False
    timerObj = None
    timerLimit = 0.0

    @staticmethod
    def start(x):
        if not (float(x) > 0.0):
            return False
            
        ThreadController.timerLimit = x
            
        if ThreadController.timerObj:
            ThreadController.stop()
            
        ThreadController.timerObj = Timer(ThreadController.timerLimit, ThreadController.stop)
        ThreadController.threadStop = False
        
        ThreadController.timerObj.start()

        return True
    
    @staticmethod
    def stop():
        if not ThreadController.timerObj:
            return False
            
        ThreadController.timerObj.cancel()
        ThreadController.threadStop = True
        #ThreadController.timerObj = None
        
        return True

    @staticmethod
    def running():
        return not ThreadController.threadStop

    @staticmethod
    def reset():
        if (ThreadController.threadStop 
        and ThreadController.timerObj is not None):
            ThreadController.threadStop = False
            ThreadController.timerObj = Timer(ThreadController.timerLimit, 
                ThreadController.stop)
            ThreadController.timerObj.start()

def getTimetables(game_id, base_airport, fleet_type, rebuild, ttMgr, fltCln):
    """loads flights and timetable data into a TimetableManager"""
   
    if (not isinstance(base_airport, Airport) 
    or  not isinstance(fleet_type, FleetType) 
    or  not isinstance(ttMgr, TimetableManager)
    or  not isinstance(fltCln, FlightCollection)):
        raise Exception("Bad args to getTimetables")
        
    cnx = connector.connect(user='mysql',  password='password', 
          host=' ', database='airwaysim')
    cursor = cnx.cursor(dictionary=True, buffered=True)        

    timetables = {}
    timetableHeaders = {}
    
    # if rebuild, existing timetables of the desired fleet type are added to 
    # the TimetableManager
    fleet_type_condition = ""
    if rebuild:
        fleet_type_condition = "AND fleet_type_id <> {}".format(fleet_type.fleet_type_id)
    
    query = '''
    SELECT timetable_id, fleet_type_id, base_airport_iata, 
    TIME_FORMAT(base_turnaround_delta, '%H:%i') AS base_turnaround_delta
    FROM timetables
    WHERE game_id = {}
    AND base_airport_iata = '{}'
    {}
    AND deleted = 'N'
    '''.format(game_id, base_airport.iata_code, fleet_type_condition)
    
    cursor.execute(query)
    
    for row in cursor:
        timetableHeaders[row['timetable_id']] = row
        if row['fleet_type_id'] not in fleet_types:
            print(row)
        timetableHeaders[row['timetable_id']]['fleet_type'] = (
            fleet_types[row['fleet_type_id']]
            )
        
        # record the number of timetables of each fleet_type_id
        if row['fleet_type_id'] not in timetableCounts:
            timetableCounts[row['fleet_type_id']] = 0
        timetableCounts[row['fleet_type_id']] += 1
    
    # create an additional SQL condition for the timetable_ids we find
    timetable_condition = ""
    if len(timetableHeaders.keys()) > 0:
        timetable_condition = "AND t.timetable_id IN ({})".format(
            ", ".join(map(str, list(timetableHeaders.keys())))
            )

    query = '''
    SELECT DISTINCT t.timetable_id, flight_number, e.start_day, 
    TIME_FORMAT(e.start_time, '%H:%i') AS start_time,
    TIME_FORMAT(e.dest_turnaround_length, '%H:%i') AS dest_turnaround_length,
    TIME_FORMAT(e.post_padding, '%H:%i') AS post_padding
    FROM timetables t, timetable_entries e
    WHERE t.timetable_id = e.timetable_id
    AND t.base_airport_iata = '{}'
    {}
    ORDER BY t.timetable_id, start_day, start_time
    '''.format(base_airport.iata_code, timetable_condition)
    
    cursor.execute(query)
    
    for row in cursor:
        if row['timetable_id'] not in timetables:
            timetables[row['timetable_id']] = Timetable(
                timetable_id=row['timetable_id'],
                base_airport=base_airport_obj, 
                fleet_type=timetableHeaders[row['timetable_id']]['fleet_type'],
                outbound_dep=row['start_time'], 
                fManager=ttManager,
                base_turnaround_delta=
                timetableHeaders[row['timetable_id']]['base_turnaround_delta'])

        entry = TimetableEntry(flight_lookup[row['flight_number']], 
            timetables[row['timetable_id']], row['post_padding'],
            row['dest_turnaround_length'])
        #print(entry)
        if entry.flight.fleet_type == timetables[row['timetable_id']].fleet_type:
            timetables[row['timetable_id']].append(entry)
        
        # if rebuild is not set, remove timetabled flights from the 
        # FlightCollection, leaving only untimetabled flights;
        # otherwise, all flights of the specified fleet type can be used
        if not rebuild:
            fltCln.delete(entry.flight)
        
    for id in timetables:
        ttManager.append(timetables[id])

def writeTimetableToDB(tt):
    if not isinstance(tt, Timetable):
        raise Exception("Bad args for writeTimetableToDB")
    
    cnx = connector.connect(user='mysql',  password='password', 
<<<<<<< .mine
          host='10.1.1.147', database='airwaysim')
=======
          host='localhost', database='airwaysim')
>>>>>>> .r39
    cursor = cnx.cursor(dictionary=True, buffered=True)
    
    # this might be the first timetable of this type at this base
    if tt.fleet_type.fleet_type_id not in timetableCounts:
        timetableCounts[tt.fleet_type.fleet_type_id] = 0
        
    timetable_name = "%s-%s-%02d" % (tt.base_airport.iata_code,
            tt.fleet_type.fleet_icao_code,
            timetableCounts[tt.fleet_type.fleet_type_id] + 1)
        
    query = '''
    INSERT INTO timetables (game_id, base_airport_iata, fleet_type_id, 
    timetable_name, base_turnaround_delta, entries_json)
    VALUES ({}, '{}', {}, '{}', '{}', '')
    '''.format(
        game_id, tt.base_airport.iata_code, tt.fleet_type.fleet_type_id,
        timetable_name,
        timedelta_to_hhmm(
            tt.base_turnaround_length - tt.fleet_type.min_turnaround
        )
    )
    #print(query)
    cursor.execute(query)
  
    timetable_id = cursor.lastrowid
    
    # timetable_entries rows
    entries = []
    
    # any required changes to flights.turnaround_length
    flight_updates = {}
    
    for x in tt.flights:
        txt = "({}, '{}', '{}', '{}', '{}', '{}', '{}')".format(
            timetable_id, x.flight.flight_number, 
            x.flight.dest_airport.iata_code,
            x.outbound_dep.strftime("%H:%M"),
            x.start_day, x.available_time.strftime("%H:%M"),
            timedelta_to_hhmm(x.post_padding)
        )
        entries.append(txt)
        
        # save adjusted dest_turnaround_lengths
        if x.dest_turnaround_length != x.flight.turnaround_length:
            flight_updates[x.flight.flight_number] = (
                "WHEN '{}' THEN '{}' ".format(
                    x.flight.flight_number,
                    timedelta_to_hhmm(x.dest_turnaround_length)
                    ))

    query = '''
    INSERT INTO timetable_entries (timetable_id, flight_number, 
    dest_airport_iata, start_time, start_day, earliest_available, post_padding)
    VALUES {}
    '''.format(", ".join(entries))
    #print(query)
    
    cursor.execute(query)
    
    # update flights with new destination turnarounds if required
    if len(flight_updates):
        query =  '''
        UPDATE flights
            SET turnaround_length = CASE flight_number
            {}
            END
        WHERE game_id = {}
        AND deleted = 'N'
        AND flight_number IN ('{}')
        '''.format(
            "\n ".join(list(flight_updates.values())),
            game_id,
            "', '".join(list(flight_updates.keys())),
        )
        
        #print(query)
        cursor.execute(query)
    
    if cnx.in_transaction:
        cnx.commit()
    cursor.close()
    cnx.close()
    
    # increment the count of timetables of this fleet type
    timetableCounts[tt.fleet_type.fleet_type_id] += 1
    
    print("Added timetable [{}] to DB".format(timetable_name))
        
        
def getBaseFlights(game_id, base_airport_iata, fleet_type_id, flightCln):    
    """loads flights and airport data into a FlightCollection"""
   
    if not isinstance(flightCln, FlightCollection):
        raise Exception("Bad args to getBaseFlights")
        
    cnx = connector.connect(user='mysql',  password='password', 
          host='localhost', database='airwaysim')
    cursor = cnx.cursor(dictionary=True, buffered=True)
    
    airport_fields = [
        'dest_airport_iata', 'iata_code', 'icao_code', 'city', 'airport_name', 
        'timezone', 'curfew_start', 'curfew_finish',
        ]
    fleet_type_fields = [
        'fleet_type_id', 'description', 'min_turnaround', 'fleet_icao_code',
        'ops_turnaround_length',
        ]
    flight_fields = [ 
        'flight_number', 'fleet_type_id', 'outbound_length', 'inbound_length', 
        'turnaround_length', 'distance_nm',
        ]   
    
    # add the base airport to the lookup
    query = '''
        SELECT DISTINCT r.base_airport_iata as iata_code, 
        a.icao_code, a.city, a.airport_name, a.timezone,
        TIME_FORMAT(c.start, '%H:%i') AS curfew_start,
        TIME_FORMAT(c.finish, '%H:%i') AS curfew_finish
        FROM routes r, airports a LEFT JOIN airport_curfews c
        ON a.icao_code = c.icao_code
        WHERE r.game_id = {}
        AND r.base_airport_iata = '{}'
        AND r.base_airport_iata = a.iata_code
        '''.format(game_id, base_airport_iata)

    cursor.execute(query)
    
    if cursor.rowcount <= 0:
        return False

    for row in cursor:
        airports[row['iata_code']] = Airport(
        { key:value for key,value in row.items() if key in airport_fields }
        )
      
    # get route data and destination airports
    query = '''
        SELECT r.route_id, r.distance_nm, r.dest_airport_iata as iata_code, 
        a.icao_code, a.city, a.airport_name, a.timezone,
        TIME_FORMAT(c.start, '%H:%i') AS curfew_start,
        TIME_FORMAT(c.finish, '%H:%i') AS curfew_finish
        FROM routes r, airports a LEFT JOIN airport_curfews c
        ON a.icao_code = c.icao_code
        WHERE r.game_id = {}
        AND r.base_airport_iata = '{}'
        AND r.dest_airport_iata = a.iata_code
        '''.format(game_id, base_airport_iata)
    
    cursor.execute(query)
    
    if cursor.rowcount <= 0:
        return False
        
    for row in cursor:
        routes[row['route_id']] = row
        
        if row['iata_code'] not in airports:
            airports[row['iata_code']] = Airport(
            { key:value for key,value in row.items() if key in airport_fields }
            )
  
    
    # get fleet_type and flight data
    query = '''
        SELECT DISTINCT 
        f.flight_number,
        f.route_id,
        ft.icao_code as fleet_icao_code,
        f.fleet_type_id,
        ft.description,
        r.dest_airport_iata as iata_code,
        TIME_FORMAT(f.outbound_length, '%H:%i') AS outbound_length,
        TIME_FORMAT(f.inbound_length, '%H:%i') AS inbound_length,
        TIME_FORMAT(f.turnaround_length, '%H:%i') AS turnaround_length,
        TIME_FORMAT(ft.turnaround_length, '%H:%i') AS min_turnaround,
        TIME_FORMAT(ft.ops_turnaround_length, '%H:%i') AS ops_turnaround_length
        FROM flights f, routes r, fleet_types ft, games g, 
        airports aa LEFT JOIN airport_curfews c
        ON aa.icao_code = c.icao_code
        WHERE ((f.route_id = r.route_id)
        AND (f.game_id = g.game_id)
        AND (f.game_id = '{}')
        AND (r.base_airport_iata = '{}')
        AND (f.turnaround_length is not null)
        AND (ft.fleet_type_id = f.fleet_type_id)
        AND (aa.iata_code = r.dest_airport_iata)
        AND (f.deleted = 'N'))
        ORDER BY flight_number
        '''.format(game_id, base_airport_iata)   

    cursor.execute(query)
    if cursor.rowcount <= 0:
        return False
        
    for row in cursor:
        #print(row)
        if row['fleet_type_id'] not in fleet_types:
            fleet_types[row['fleet_type_id']] = FleetType({
                key:value for key,value in row.items() 
                    if key in fleet_type_fields 
                })
            
        f = { key:value for key,value in row.items() 
                if key in flight_fields 
            }

        f['dest_airport'] = airports[row['iata_code']]
        f['base_airport'] = airports[base_airport_iata]
        f['fleet_type'] = fleet_types[row['fleet_type_id']]
        f['distance_nm'] = routes[row['route_id']]['distance_nm']

        newFlight = Flight(f)
        flight_lookup[row['flight_number']] = newFlight
        #print(newFlight.turnaround_length, f['turnaround_length'])
        
        # only flights with desired fleet_type_id added to collection
        if row['fleet_type_id'] == fleet_type_id:
            flightCln.append(newFlight)

    # add maintenance flight
    MTXFlight = MaintenanceCheckA(airports[base_airport_iata], 
        fleet_types[fleet_type_id])
    flightCln.append(MTXFlight)
    flight_lookup['MTX'] = MTXFlight

    return True
    
    
def add_flight(tt, fltCln, ttMgr):
    if (not isinstance(tt, Timetable)
    or  not isinstance(fltCln, FlightCollection) 
    or  not isinstance(ttMgr, TimetableManager)):
        raise Exception("Bad argument passed to add_flight")

    if tt.is_good(threshold):
        return tt
        
    if not ThreadController.running():
        #pdb.set_trace()
        #ThreadController.reset()
        return None
    
    # if the tt size exceeds the maximum, spit back nothing
    if (tt.total_time().total_seconds() > 7 * 86400):
        return None
        
    #print(tt)
        
    t2 = None
    for f in fltCln:
        if tt.isEmpty():
            pass
            #pdb.set_trace()
            #print("Starting timetable with {}".format(str(f)))
        #pdb.set_trace()
        entry = TimetableEntry(f, tt)

        if entry.is_good():
            fltCln.delete(f)
            ttMgr.append(entry)
            t2 = add_flight(tt + entry, fltCln, ttMgr) 
            if t2:
                break
            else:
                fltCln.undelete(f)
                ttMgr.remove(entry)

    return t2

    
def usage():
    print(
    "Usage: {} [-g/game-id=] <game-id>\n"
      "\t\t[-b/--base=] <base-iata-code>\n"
      "\t\t[-f/--fleet-type=] <icao fleet code> ({})\n"
      "\t\t[-s/--start-time] <HH:MM>\n"
      "\t\t[-t/--threshold=] <0.0000-0.9999>\n"
      "\t\t[-m/-max-range=] <max range allowed>\n"
      "\t\t[-c/--count=] <no. of timetables to create (default=1)\n"
      "\t\t[-d/--turnaround_delta=] <HH:MM> add to min.turnaround at base\n"
      "\t\t[-r/--rebuild] rebuild all timetables at base\n"
      "\t\t[-w/--write] write to database\n".format(sys.argv[0],
      "|".join(sorted(list(types.keys())))));


if __name__ == '__main__':    
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hg:b:f:s:t:m:c:d:rw",
            ["game-id=","base=", "fleet-type=", "start-time=", "threshold=", 
            "max-range=", "count=", "turnaround-delta=", "rebuild", "write",
            ])
    except getopt.GetoptError as err:
        print(err)  
        usage()
        sys.exit(2)

    game_id = base = fleet_type_id = None
    start_time = "06:40"
    base_turnaround_delta = None
    threshold = 0.99
    max_range = None
    count = 1
    rebuild_all = False
    writeToDatabase = False

    
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-g", "--game-id"):
            game_id = a
        elif o in ("-b", "--base"):
            base = a.upper()
        elif o in ("-f", "--fleet-type"):
            fleet_type_id = types.get(a.upper(), None)
        elif o in ("-s", "--start-time"):
            start_time = a
        elif o in ("-d", "--turnaround-delta"):
            base_turnaround_delta = a
        elif o in ("-t", "--threshold"):
            threshold = float(a)
        elif o in ("-m", "--max-range="):
            max_range = int(a)
            if max_range <= 0:
                usage()
                sys.exit(1)
        elif o in ("-c", "--count="):
            count = int(a)
            if count < 0:
                usage()
                sys.exit(1)
        elif o in ("-r", "--rebuild"):
            rebuild_all = True
        elif o in ("-w", "--write"):
            writeToDatabase = True
        else:
            assert False, "unhandled option"

    print(game_id, base, fleet_type_id, start_time, threshold, 
        base_turnaround_delta, max_range, rebuild_all, writeToDatabase)
    
    if not game_id or not base or not fleet_type_id:
        usage()
        sys.exit()
        
    if not getBaseFlights(game_id, base, fleet_type_id, flightColl):
        print("No results for those args")
        sys.exit(3)
    
    base_airport_obj = airports[base]
    fleet_type = fleet_types[fleet_type_id]

    getTimetables(game_id, base_airport_obj, fleet_type, rebuild_all, 
        ttManager, flightColl)

 
    print(flightColl.status())
    
    all_timetables = []
    tt = Timetable(None, base_airport_obj, fleet_type, start_time, ttManager, 
        base_turnaround_delta, max_range)
    #print(add_flight(tt))
    
    #sys.exit(1)
    
    # not seen at this time vv
    retryCount = 0
    old_index = 0
    index = 1
    while True:
        TimeLimit = 30.0 * index

        fib = old_index
        old_index = index
        index = old_index + fib
        
        if retryCount > 4000:
            print("No more!")
            break
            
        print("Running for max {} s; len(all_timetables) = {}".format(
            TimeLimit, len(all_timetables)))
            
        if flightColl.total_time().total_seconds() < 6 * 86400:
            print("Less than 7 days flights remain {} - terminating".format(flightColl.total_time()))
            break
        
        ThreadController.start(TimeLimit)

        print("Before: {} entries; {}".format(len(flightColl), flightColl.total_time()))
        
        newTimetable = add_flight(tt, flightColl, ttManager)
        
        ThreadController.stop()

        #print(newTimetable)
        if newTimetable:
            print("After: {} entries; {}\n".format(len(flightColl), flightColl.total_time()))

            tt.available_time += timedelta(minutes=5)
            all_timetables.append(newTimetable)
            flightColl.undelete(flight_lookup['MTX'])
            
            if count > 0 and len(all_timetables) >= count:
                break

        else:
            retryCount += 1
    
            while len(all_timetables) > 0:
                #delete the last timetable from the list
                deleted = all_timetables.pop()
                
                # the flights can no longer be used for conflict checks
                ttManager.remove(deleted)
                
                # remove the flights from the flight collection
                for x in deleted.flights:
                    flightColl.undelete(x.flight)
            
            # now we can restart the process from the index-1 th timetable
            tt.available_time = str_to_nptime(start_time)
            print("Removing all timetables and starting again\n")
            if (index >= 2):
                index = old_index = 1
    
    
    for a in all_timetables:
        print(str(a))
        if writeToDatabase:
            writeTimetableToDB(a)
    #ttManager.remove(tt)

    #print(flightColl.status())
    #flightColl.reset()
    #print(flightColl.status())    
