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
        print("Start")
       
        ThreadController.timerObj.start()

        return True
    
    @staticmethod
    def stop():
        if not ThreadController.timerObj:
            return False
            
        ThreadController.timerObj.cancel()
        ThreadController.threadStop = True
        ThreadController.timerObj = None
        print("Timeout")
        
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

            
class TimetableBuilder:
    def __init__(self, game_id, use_rejected=False, shuffle=True, db_user='mysql', 
        db_pass='password', db_host='localhost', db_name='airwaysim',
        db_port=3306):
        # all timetables at all bases
        # stored as timetables[base_airport_iata][fleet_type_id]
        self.timetables = {}
        
        # all flights at all bases
        # stored as flights[base_airport_iata][fleet_type_id]
        self.flights = {}
        self.airports = {}
        self.fleet_types = {}
        self.routes = {}
        self.ttManager = TimetableManager()
        self.rejected = []
        self.use_rejected = use_rejected
        self.MTXFlights = {}
        self.shuffle_flights = shuffle
        self.game_id = game_id
        
        self.db_user = db_user
        self.db_pass = db_pass
        self.db_host = db_host
        self.db_name = db_name
        self.db_name = db_name
        self.db_port = db_port
        
        self.getFlights()
        self.getTimetables()
        
    def refresh(self):
        pass

    def getFlights(self):
        cnx = connector.connect(user=self.db_user,  password=self.db_pass, 
              host=self.db_host, database=self.db_name)
        cursor = cnx.cursor(dictionary=True)
        
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
            
        self.flight_lookup = {}

        
        # add the base airport to the lookup
        query = '''
            SELECT DISTINCT r.base_airport_iata as iata_code, 
            a.icao_code, a.city, a.airport_name, a.timezone,
            TIME_FORMAT(c.start, '%H:%i') AS curfew_start,
            TIME_FORMAT(c.finish, '%H:%i') AS curfew_finish
            FROM routes r, airports a LEFT JOIN airport_curfews c
            ON a.icao_code = c.icao_code
            WHERE r.game_id = {}
            AND r.base_airport_iata = a.iata_code
            '''.format(self.game_id)
        cursor.execute(query)
        

        for row in cursor:
            #print(row)
            self.airports[row['iata_code']] = Airport(
            { key:value for key,value in row.items() if key in airport_fields }
            )
            
        if len(self.airports.keys()) == 0:
            return False
          
        # get route data and destination airports
        query = '''
            SELECT r.route_id, r.distance_nm, r.dest_airport_iata as iata_code, 
            a.icao_code, a.city, a.airport_name, a.timezone,
            TIME_FORMAT(c.start, '%H:%i') AS curfew_start,
            TIME_FORMAT(c.finish, '%H:%i') AS curfew_finish
            FROM routes r, airports a LEFT JOIN airport_curfews c
            ON a.icao_code = c.icao_code
            WHERE r.game_id = {}
            AND r.dest_airport_iata = a.iata_code
            '''.format(self.game_id)

        cursor.execute(query)
        
        for row in cursor:
            self.routes[row['route_id']] = row
            
            if row['iata_code'] not in self.airports:
                self.airports[row['iata_code']] = Airport(
                { key:value for key,value in row.items() if key in airport_fields }
                )
        
        if len(self.routes) == 0:
            return False
            
        # get fleet_type and flight data
        query = '''
            SELECT DISTINCT 
            f.flight_number,
            f.route_id,
            ft.icao_code as fleet_icao_code,
            f.fleet_type_id,
            ft.description,
            r.base_airport_iata, r.dest_airport_iata,
            TIME_FORMAT(f.outbound_length, '%H:%i') AS outbound_length,
            TIME_FORMAT(f.inbound_length, '%H:%i') AS inbound_length,
            TIME_FORMAT(f.turnaround_length, '%H:%i') AS turnaround_length,
            TIME_FORMAT(ft.turnaround_length, '%H:%i') AS min_turnaround,
            TIME_FORMAT(ft.ops_turnaround_length, '%H:%i') AS ops_turnaround_length
            FROM flights f, routes r, fleet_types ft, games g, 
            airports a, airports aa
            WHERE ((f.route_id = r.route_id)
            AND (f.game_id = g.game_id)
            AND (f.game_id = '{}')
            AND (f.turnaround_length is not null)
            AND (ft.fleet_type_id = f.fleet_type_id)
            AND (a.iata_code = r.base_airport_iata)
            AND (aa.iata_code = r.dest_airport_iata)
            AND (f.deleted = 'N'))
            ORDER BY flight_number
            '''.format(self.game_id)   

        cursor.execute(query)

        for row in cursor:
            #print(row)
            base_airport_iata = row['base_airport_iata']
            fleet_type_id = row['fleet_type_id']
            flight_number = row['flight_number']
            
            # self.flights[row['base_airport_iata']]
            if base_airport_iata not in self.flights:
                self.flights[base_airport_iata] = {}
                
            if fleet_type_id not in self.fleet_types:
                self.fleet_types[fleet_type_id] = FleetType({
                    key:value for key,value in row.items() 
                        if key in fleet_type_fields 
                    })
                    
            # self.flights[row['base_airport_iata']][row['fleet_type_id']]
            if fleet_type_id not in self.flights[base_airport_iata]:
                self.flights[base_airport_iata][fleet_type_id] = (
                    FlightCollection(self.shuffle_flights)
                )

            # get the FlightCollection for this base/fleet-type pair
            flightCln = self.flights[base_airport_iata][fleet_type_id]
                
                
            # get flight details
            f = { key:value for key,value in row.items() 
                    if key in flight_fields 
                }

            f['base_airport'] = self.airports[row['base_airport_iata']]
            f['dest_airport'] = self.airports[row['dest_airport_iata']]

            f['fleet_type'] = self.fleet_types[row['fleet_type_id']]
            f['distance_nm'] = self.routes[row['route_id']]['distance_nm']

            self.flight_lookup[flight_number] = Flight(f)
            
            # only flights with desired fleet_type_id added to collection
            flightCln.append(self.flight_lookup[flight_number])

        if len(self.flight_lookup.keys()) == 0:
            return False
            
        # add maintenance flights to each FlightCollection
        for base_airport_iata in self.flights:
            self.MTXFlights[base_airport_iata] = {}
            for fleet_type_id in self.flights[base_airport_iata]:
                mtx = self.MTXFlights[base_airport_iata][fleet_type_id] = (
                    MaintenanceCheckA(self.airports[base_airport_iata], 
                    self.fleet_types[fleet_type_id])
                    )
                flightCln = self.flights[base_airport_iata][fleet_type_id]
                flightCln.append(mtx)

        return True
 
 
    def getTimetables(self):
        """loads flights and timetable data into a TimetableManager"""
            
        cnx = connector.connect(user=self.db_user, password=self.db_pass, 
              host=self.db_host, database=self.db_name)
        cursor = cnx.cursor(dictionary=True)        

        timetables = {}
        tHdrs = {}
        
        query = '''
        SELECT timetable_id, fleet_type_id, base_airport_iata, 
        TIME_FORMAT(base_turnaround_delta, '%H:%i') AS base_turnaround_delta
        FROM timetables
        WHERE game_id = {}
        AND deleted = 'N'
        '''.format(self.game_id)
        
        cursor.execute(query)
        
        for row in cursor:
            tHdrs[row['timetable_id']] = row
            if row['fleet_type_id'] not in self.fleet_types:
                print(row)
                
            # add airport and fleet-type objects
            tHdrs[row['timetable_id']]['fleet_type'] = (
                self.fleet_types[row['fleet_type_id']]
                )
            tHdrs[row['timetable_id']]['base_airport'] = (
                self.airports[row['base_airport_iata']]
                )
                
        # create an additional SQL condition for the timetable_ids we find
        timetable_condition = ""
        if len(tHdrs.keys()) > 0:
            timetable_condition = "AND t.timetable_id IN ({})".format(
                ", ".join(map(str, list(tHdrs.keys())))
                )

        query = '''
        SELECT DISTINCT t.timetable_id, flight_number, e.start_day, 
        TIME_FORMAT(e.start_time, '%H:%i') AS start_time,
        TIME_FORMAT(e.dest_turnaround_length, '%H:%i') AS dest_turnaround_length,
        TIME_FORMAT(e.post_padding, '%H:%i') AS post_padding
        FROM timetables t, timetable_entries e
        WHERE t.timetable_id = e.timetable_id
        {}
        ORDER BY t.timetable_id, start_day, start_time
        '''.format(timetable_condition)
        
        cursor.execute(query)
        
        for row in cursor:
            timetable_id = row['timetable_id']
            base_airport_iata = tHdrs[timetable_id]['base_airport'].iata_code
            fleet_type_id = tHdrs[timetable_id]['fleet_type'].fleet_type_id

            if timetable_id not in timetables:
                timetables[timetable_id] = Timetable(
                    timetable_id=timetable_id,
                    base_airport=
                        tHdrs[timetable_id]['base_airport'], 
                    fleet_type=
                        tHdrs[timetable_id]['fleet_type'],
                    outbound_dep=row['start_time'], 
                    fManager=self.ttManager,
                    base_turnaround_delta=
                        tHdrs[timetable_id]['base_turnaround_delta'])

            # flight_lookup fails for MTX
            if row['flight_number'] == 'MTX':
                flight = self.MTXFlights[base_airport_iata][fleet_type_id]
            else:
                flight = self.flight_lookup[row['flight_number']]
            entry = TimetableEntry(flight, 
                timetables[timetable_id], row['post_padding'],
                row['dest_turnaround_length'])
            #print(entry.flight)
            if entry.flight.fleet_type == timetables[timetable_id].fleet_type:
                timetables[row['timetable_id']].append(entry)
            else:
                raise Exception("Bad flight for TimetableEntry {}".format(entry.flight))
            
            
        # add all timetables to the TimetableManager and create self.timetables
        self.timetables = {}
        for id in timetables:
            self.ttManager.append(timetables[id])
            
            # self.timetables
            tt = timetables[id]
            base_airport_iata = tt.base_airport.iata_code
            fleet_type_id = tt.fleet_type.fleet_type_id
            if base_airport_iata not in self.timetables:
                self.timetables[base_airport_iata] = {}
            if fleet_type_id not in self.timetables[base_airport_iata]:
                self.timetables[base_airport_iata][fleet_type_id] = []
            self.timetables[base_airport_iata][fleet_type_id].append(tt)
            
          
    def add_flight(self, tt, ttManager):
        if tt.is_good(self.threshold):
            return tt
            
        # if the tt size exceeds the maximum, spit back nothing
        if (tt.total_time().total_seconds() > 7 * 86400):
            return None
            
        #print(tt)
        
        fltCln = (
            self.flights[tt.base_airport.iata_code][tt.fleet_type.fleet_type_id]
            )
            
        t2 = None
        for f in fltCln:
            if not ThreadController.running():
                #pdb.set_trace()
                ThreadController.reset()
                return None

            if tt.isEmpty():
                #pass
                #pdb.set_trace()
                print("Starting timetable with {}".format(str(f)))
            #pdb.set_trace()
            entry = TimetableEntry(f, tt)

            if not entry.is_good():
                continue
                
            newTT = tt + entry
            ##print(newTT)
            
            #import pdb; pdb.set_trace()
            
            # ignore already rejected combinations
            if self.use_rejected and newTT.lex() in self.rejected:
                #print("Rejecting [{}]".format(newTT.lex()))
                continue

            fltCln.delete(f)
            ttManager.append(entry)
            t2 = self.add_flight(newTT, ttManager) 
            if t2:
                break
            else:
                fltCln.undelete(f)
                ttManager.remove(entry)
                self.rejected.append(newTT.lex())
                #print("Rej: [{}] = [{}]".format(newTT.seq(), newTT.lex()))

        return t2
        
    def __call__(self, base_airport_iata, fleet_type_id, start_time, 
        base_turnaround_delta=None, threshold=0.95, rebuild=False, count=1, 
        max_range=None, exclude_flights=None):
        """verify args"""
        
        if (base_airport_iata not in self.flights
        or  fleet_type_id not in self.flights[base_airport_iata]):
            raise Exception("__call__ args: base_airport_iata = {}; "
            "fleet_type_id = {}".format(base_airport_iata, fleet_type_id))
            
        if not str_to_nptime(start_time):
            raise Exception("__call__ args: start_time={}".format(start_time))
            
        if threshold < 0.90 or threshold > 1.0:
            raise Exception("Bad threshold for TimetableBuilder: {}".format(threshold))
            
        self.threshold = threshold
            
        base_airport_obj = self.airports[base_airport_iata]
        fleet_type = self.fleet_types[fleet_type_id]
        
        all_timetables = []

       
        fltCln = self.flights[base_airport_iata][fleet_type_id]
        ttMgr = self.ttManager
        
        # if rebuild is not set, we remove timetabled flights from fltCln
        if (not rebuild 
            and base_airport_iata in self.timetables 
            and fleet_type_id in self.timetables[base_airport_iata]):
            print("Deleting {}, {} from fltCln".format(base_airport_iata, fleet_type_id))
            for ttObj in self.timetables[base_airport_iata][fleet_type_id]:
                for ttEntryObj in ttObj.flights:
                    fltCln.delete(ttEntryObj.flight)
        else:
            fltCln.reset()

            # create our filtered TimetableManager, excluding the flights from
            # this base/fleet type
            ttMgr = self.ttManager.filter(base_airport_iata, fleet_type_id)
            
       
        # if a list of excluded flight numbers is supplied, we delete them from
        # the FlightCollection
        if isinstance(exclude_flights, list):
            exclude_flights = [s.upper() for s in exclude_flights]
            for x in exclude_flights:
                if x != 'MTX' and x in self.flight_lookup:
                    print("Excluding {}".format(self.flight_lookup[x]))
                    fltCln.delete(self.flight_lookup[x])

        tt = Timetable(None, self.airports[base_airport_iata], 
            self.fleet_types[fleet_type_id], start_time, 
            ttMgr, base_turnaround_delta, max_range)
         
        
           
        # not seen at this time vv
        retryCount = 0
        old_index = 0
        index = 1
        while True:
            TimeLimit = 60.0# * index

            fib = old_index
            old_index = index
            index = old_index + fib
            
            if retryCount > 4000:
                print("No more!")
                break
                
            print("Running for max {} s; len(all_timetables) = {}".format(
                TimeLimit, len(all_timetables)))
                
            if fltCln.total_time().total_seconds() < 6 * 86400:
                print("Less than 7 days flights remain {} - terminating".format(fltCln.total_time()))
                break
            
            ThreadController.start(TimeLimit)

            print("Before: {} entries; {}".format(len(fltCln), fltCln.total_time()))
            self.rejected = []
            newTimetable = self.add_flight(tt, ttMgr)
            
            ThreadController.stop()

            #print(newTimetable)
            if newTimetable:
                print("After: {} entries; {}\n".format(len(fltCln), fltCln.total_time()))
                all_timetables.append(newTimetable)
                fltCln.releaseMTX()
                
                if count > 0 and len(all_timetables) >= count:
                    break
                else:
                    tt.available_time += timedelta(minutes=5)
            else:
                retryCount += 1
        
                if len(all_timetables) > 0:
                    #delete the last timetable from the list
                    deleted = all_timetables.pop()
                    
                    # the flights can no longer be used for conflict checks
                    ttMgr.remove(deleted)
                    
                    # remove the flights from the flight collection
                    for x in deleted.flights:
                        fltCln.undelete(x.flight)
                
                # now we can restart the process from the index-1 th timetable
                #tt.available_time = str_to_nptime(start_time)
                
                if not self.shuffle_flights:
                    print("Aborting - all possible options exhausted")
                    break

                print("Removing all timetables and starting again\n")
                print("Deleting last timetable and starting again")
                if (index >= 2):
                    index = old_index = 1
        
        
        for a in all_timetables:
            print(str(a))
            #if self.writeToDatabase:
            #    writeTimetableToDB(a)
        #ttManager.remove(tt)

        #print(fltCln.status())
        #fltCln.reset()
        #print(fltCln.status())    




    def writeTimetableToDB(self, tt):
        if not isinstance(tt, Timetable):
            raise Exception("Bad args for writeTimetableToDB")
        
        cnx = connector.connect(user=self.db_user, password=self.db_pass, 
              host=self.db_host, database=self.db_name)
        cursor = cnx.cursor(dictionary=True, buffered=True)
        
        # this might be the first timetable of this type at this base
        fleet_type_id = tt.base_airport.iata_code
        base_airport_iata = tt.fleet_type.fleet_type_id
        if base_airport_iata not in self.timetables:
            self.timetables[base_airport_iata] = {}
        if fleet_type_id not in self.timetables[base_airport_iata]:
            self.timetables[base_airport_iata][fleet_type_id] = []
            
        timetable_name = "%s-%s-%02d" % (base_airport_iata,
                tt.fleet_type.fleet_icao_code,
                len(timetables[base_airport_iata][fleet_type_id]) + 1)
            
        query = '''
        INSERT INTO timetables (game_id, base_airport_iata, fleet_type_id, 
        timetable_name, base_turnaround_delta, entries_json)
        VALUES ({}, '{}', {}, '{}', '{}', '')
        '''.format(
            self.game_id, base_airport_iata, fleet_type_id, timetable_name,
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
                self.game_id,
                "', '".join(list(flight_updates.keys())),
            )
            
            #print(query)
            cursor.execute(query)
        
        if cnx.in_transaction:
            cnx.commit()
        cursor.close()
        cnx.close()
        
        timetables[base_airport_iata][fleet_type_id].append(tt)
        
        print("Added timetable [{}] to DB".format(timetable_name))
            
        

    



    
