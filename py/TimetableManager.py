# -*- coding: utf-8 -*-
"""
Created on Fri Jan 20 19:47:58 2017

@author: Delano
"""
from flights import FlightManager
from timetables import Timetable, TimetableEntry
import re
from nptools import str_to_timedelta, nptime_diff_sec
from datasources import DataSource


"""
TimetableManager

* loads all available timetables from provided source
* looks for conflicts between a timetable entry and all other entries

self.timetables - 
    map of all timetables indexed by base airport and fleet type id
    self.timetables[base_airport_iata][fleet_type_id] = [timetable, ...]
    
self.routes -
    lookup of flights between each timetabled city pair (e.g. LHR-JFK)
    
    self.routes['LHR-JFK']['QV001'] = {
            'flight': <Flight> object,
            'outbound_dep': 16:00,
            'inbound_dep': 22:00,
            'refCount': 1
    }    
"""
class TimetableManager:

    def __init__(self, source=None, ftManager=None, build=True):
        print(source, ftManager)
        # if we have FlightManager, use it and its source
        if isinstance(ftManager, FlightManager):
            self.fMgr = ftManager
            self.source = self.fMgr.source
        else:
            # use source to create new FlightManager
            if not isinstance(source, DataSource):
                raise Exception("TimetableManager: No data source provided")
            self.source = source
            self.fMgr = FlightManager(self.source)
            self.fMgr.getFlights()
           
        self.game_id = self.source.game_id        
        self.routes = {}
        self.ignore_base_timetables = False
        self.timetables = {}
        
        if build:        
            self.getTimetables()

        
    def setIgnoreBaseTimetables(self, status):
        if not isinstance(status, bool):
            raise Exception("Bad value passed to setIgnoreBaseTimetables")
            
        self.ignore_base_timetables = status

    """
    loads flights and timetable data into a TimetableManager
    """
    def getTimetables(self):
        timetables = {}

        data = self.source.getTimetables()

        for tt in data:
            timetable_id = tt['timetable_id']

            if tt['fleet_type_id'] not in self.fMgr.fleet_types:
                print(tt)

            base_airport_iata = tt['base_airport_iata']
            fleet_type_id = tt['fleet_type_id']
            fleet_type = self.fMgr.fleet_types[fleet_type_id]

            timetables[timetable_id] = Timetable(self,
                timetable_id=timetable_id,
                game_id=self.game_id,
                timetable_name=tt['timetable_name'],
                base_airport=self.fMgr.airports[tt['base_airport_iata']],
                fleet_type=fleet_type,
                outbound_dep=tt["entries"][0]['start_time'],
                base_turnaround_delta=tt['base_turnaround_delta'])

            for row in tt["entries"]:
                # flight_lookup fails for MTX
                # dest_turnaround is bogus
                dt = (str_to_timedelta(row['dest_turnaround_padding']) +
                      fleet_type.ops_turnaround_length)
                if row['flight_number'] == 'MTX':
                    flight = self.fMgr.MTXFlights[base_airport_iata] \
                            [fleet_type_id]
                else:
                    flight = self.fMgr.flight_lookup[
                        row['flight_number']][fleet_type_id]
                entry = TimetableEntry(flight,
                                       timetables[timetable_id],
                                       row['post_padding'], dt)
                # row['dest_turnaround_padding'])
                if entry.flight.fleet_type == timetables[
                    timetable_id].fleet_type:
                    timetables[timetable_id].append(entry)
                else:
                    raise Exception(
                        "Bad flight for timetable_id [{}]: TimetableEntry {}".
                        format(timetable_id, entry.flight))

        # add all timetables to the TimetableManager and create self.timetables
        for id in timetables:
            self.append(timetables[id])

            # self.timetables
            tt = timetables[id]
            base_airport_iata = tt.base_airport.iata_code
            fleet_type_id = tt.fleet_type.fleet_type_id
            if base_airport_iata not in self.timetables:
                self.timetables[base_airport_iata] = {}
            if fleet_type_id not in self.timetables[base_airport_iata]:
                self.timetables[base_airport_iata][fleet_type_id] = []
            self.timetables[base_airport_iata][fleet_type_id].append(tt)

        # print(self.ttManager)

        return True
        
    """
    create FlightCollection for given base/fleet pair
    """
    def getFlightCollection(self, base_airport_iata, fleet_type_id,
                            exclude_flights=None):
        if (base_airport_iata not in self.fMgr.flights 
         or fleet_type_id not in self.fMgr.flights[base_airport_iata]):
            return None
        
        fltCln = self.fMgr.flights[base_airport_iata][fleet_type_id].clone()

        # a single flight number may be operated by multiple fleet_types;
        # remove all timetabled flights in other fleet_type_id values
        if base_airport_iata in self.timetables.keys():
            flTypes = filter(lambda q: q != fleet_type_id,
                             self.timetables[base_airport_iata].keys())
            for f in flTypes:
                for x in self.timetables[base_airport_iata][f]:
                    for e in x.flights:
                        if e.flight.flight_number != "MTX":
                            # print("Deleting "+str(e.flight))
                            fltCln.deleteByFlightNumber(e.flight.flight_number)
        
        # if ignore_base_timetables is not set, we remove timetabled
        # flights from fltCln
        if (not self.ignore_base_timetables
            and base_airport_iata in self.timetables
            and fleet_type_id in self.timetables[base_airport_iata]):
            for ttObj in self.timetables[base_airport_iata][fleet_type_id]:
                for ttEntryObj in ttObj.flights:
                    fltCln.delete(ttEntryObj.flight)
        else:
            fltCln.reset()

        # if list of excluded flight numbers is supplied, delete them from
        # the FlightCollection
        if isinstance(exclude_flights, list):
            exclude_flights = [s.upper() for s in exclude_flights]
            for x in exclude_flights:
                if isinstance(x, str) and x != 'MTX':
                    fltCln.deleteByFlightNumber(x)
                    
        return fltCln


    """
    adds an entry with outbound and inbound departure times for each
    timetable entry it receives; can handle either TimetableEntry or
    Timetable objects as argument
    """
    def append(self, obj):
        if isinstance(obj, TimetableEntry):
            entries = [obj]
        elif isinstance(obj, Timetable):
            entries = obj.flights
        else:
            raise Exception("Bad arg passed to TimetableManager.append")
        
        for ttEntry in entries:
            # maintenance cannot have conflicts; there can be only one
            if ttEntry.flight.isMaintenance:
                continue

            # route pairs e.g. LHR-JFK
            key = "{}-{}".format(ttEntry.flight.base_airport.iata_code,
                ttEntry.flight.dest_airport.iata_code)

            # allow duplicates, but keep count of the references
            if key in self.routes:
                found = False
                for k, x in self.routes[key].items():
                    if x['flight'] == ttEntry.flight:
                        x['refCount'] += 1
                        found = True
                        break # for x in self.routes[key]:
                if found:
                    continue # for ttEntry in entries
            else:
                # add new route pair key                
                #self.routes[key] = []
                self.routes[key] = {}
                #print("TimetableManager.append adding {}".format(key))

            m = {}
            m['flight'] = ttEntry.flight
            m['outbound_dep'] = ttEntry.outbound_dep
            m['inbound_dep'] = ttEntry.inbound_dep
            m['refCount'] = 1
                       

            # add this flight to the route pair
            #self.routes[key].append(m)
            self.routes[key][m['flight'].flight_number] = m
            #print(key, self.routes[key])
            #print("TimetableManager.append {} {} ({})".format(key, m['flight'].flight_number,
            #      len(self.routes[key])))
            
        
    def remove(self, obj):
        if isinstance(obj, TimetableEntry):
            entries = [obj]
        elif isinstance(obj, Timetable):
            entries = obj.flights
        else:
            raise Exception("Bad arg passed to TimetableManager.remove")
        #print("deleting {} {}-{} from TimetableManager".format(
        #    obj.flight.flight_number, obj.flight.base_airport.iata_code,
        #    obj.flight.dest_airport.iata_code))

        for ttEntry in entries:
            # maintenance cannot have conflicts; there can be only one
            if ttEntry.flight.isMaintenance:
                continue
            
            # route pairs e.g. LHR-JFK
            key = "{}-{}".format(ttEntry.flight.base_airport.iata_code,
                ttEntry.flight.dest_airport.iata_code)

            if not key in self.routes:
                continue

            #print("Removing {:<8} from flightmanager".
             #   format(ttEntry.flight.flight_number))
                
            # decrement the reference count, and delete entry if needed
            for k,x in self.routes[key].items():
                if x['flight'] == ttEntry.flight:
                    x['refCount'] -= 1
                    if x['refCount'] == 0:
                        del self.routes[key][k]
                    break # for x in self.routes[key]:


    """
    create new TimetableManager instance, utilising flights with the
    specified base_airport_iata, but excluding a given fleet_type_id
    """
    def filter(self, base_airport_iata, fleet_type_id):
        out = TimetableManager(source=self.source, ftManager=self.fMgr, 
                               build=False)
        out.timetables = self.timetables
        
        pattern = re.compile(base_airport_iata)
        for key in sorted(self.routes):
            if pattern.search(key):
                #print("route {}".format(key))
                for k,f in self.routes[key].items():
                    if f['flight'].fleet_type.fleet_type_id != fleet_type_id:
                        if not key in out.routes:
                            out.routes[key] = {}
                        out.routes[key][k] = f
            else:
                pass
                #print("No [{}] in [{}]".format(base_airport_iata, key))
        #print("Filter complete")
        return out       
                
        
        
    def __str__(self):
        out = ""
        for key in self.routes:
            out += "\n{} :: ".format(key)
            l = ""
            for f, x in self.routes[key].items():
                l += "{} [{}], ".format(str(x['flight']), x['refCount'])
            out += l
           
        return out

    """
    this function replicates the PHP code of similar function;
    
    looks for conflicts between a timetable entry and all other entries
    """    
    def hasConflicts(self, ttEntry):
        debug = False
        if not isinstance(ttEntry, TimetableEntry):
            raise Exception("Bad arg passed to TimetableManager.hasConflicts")

        # maintenance cannot have conflicts; there can be only one
        if ttEntry.flight.isMaintenance:
            return False        

        # check timetables from this base if ignore_base_timetables not set
        if not self.ignore_base_timetables:
            key = "{}-{}".format(ttEntry.flight.base_airport.iata_code,
                ttEntry.flight.dest_airport.iata_code)

            # no conflict for new routes
            if not key in self.routes:
                return False
                
            # refuse duplicates
            #print("hasConflicts {}: {}".format(key, self.routes[key]))
            for k, x in self.routes[key].items():
                if x['flight'] == ttEntry.flight:
                    if debug:
                        print("!!conflict: already in use {}".format(
                            str(ttEntry.flight)))
                    return True
                    
                # check for flights less than 60 minutes apart
                d = nptime_diff_sec(ttEntry.outbound_dep, x['outbound_dep'])
                if debug:
                    print("C({}): {}-{} (OUT {}/{}) :: (OUT {}/{})".format(d,
                        ttEntry.flight.base_airport.iata_code, 
                        ttEntry.flight.dest_airport.iata_code, 
                        ttEntry.flight.flight_number, ttEntry.outbound_dep, 
                        x['flight'].flight_number, x['outbound_dep']))
                if d < 3600:
                    return True

                d = nptime_diff_sec(ttEntry.inbound_dep, x['inbound_dep'])
                if debug:
                    print("C({}): {}-{} (IN {}/{}) :: (IN {}/{})".format(d,                    
                        ttEntry.flight.base_airport.iata_code, 
                        ttEntry.flight.dest_airport.iata_code, 
                        ttEntry.flight.flight_number, ttEntry.inbound_dep, 
                        x['flight'].flight_number, x['inbound_dep']))
                if d < 3600:
                    return True
                    
        # look also for flights in the reverse direction
        rkey = "{}-{}".format(ttEntry.flight.dest_airport.iata_code,
            ttEntry.flight.base_airport.iata_code)

        # will happen in 99% of cases
        if not rkey in self.routes:
            return False
            
        # refuse duplicates
        for k,x in self.routes[rkey].items():
            # check for flights less than 60 minutes apart
            d = nptime_diff_sec(ttEntry.outbound_dep, x['inbound_dep'])
            if debug:
                print("C({}): {}-{} (OUT {}/{}) :: (IN {}/{})".format(d,              
                    ttEntry.flight.base_airport.iata_code, 
                    ttEntry.flight.dest_airport.iata_code, 
                    ttEntry.flight.flight_number, ttEntry.outbound_dep, 
                    x['flight'].flight_number, x['inbound_dep']))
            if d < 3600:
                return True

            e = nptime_diff_sec(ttEntry.inbound_dep, x['outbound_dep'])
            if debug:
                print("C({}): {}-{} (IN {}/{}) :: (OUT {}/{})".format(e,
                    ttEntry.flight.base_airport.iata_code, 
                    ttEntry.flight.dest_airport.iata_code, 
                    ttEntry.flight.flight_number, ttEntry.inbound_dep, 
                    x['flight'].flight_number, x['outbound_dep']))
            if e < 3600:
                return True
                
        return False    