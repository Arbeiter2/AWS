from datetime import timedelta
from nptime import nptime
from nptools import str_to_timedelta, str_to_nptime, TimeIsInWindow
from datasources import DataSource
import random as rnd
from functools import reduce
import simplejson as json
#from copy import deepcopy

"""
utility class for checking operational hours for takeoffs and landings
"""
class OpTimes:
    """avoid takeoffs or landings at times passengers dislike, so we check """
    """whether those times fall within these "ops" curfew times"""
    """departure curfew: 00:30 - 05:30"""
    """arrival curfew: 00:45 - 05:00"""
    EarliestDep = nptime(5, 45)
    LatestDep = nptime(0, 30)

    EarliestArr = nptime(5, 00)
    LatestArr = nptime(0, 30)

    @staticmethod
    def InDepCurfew(t):
        if not isinstance(t, nptime):
            return False

        return TimeIsInWindow(t, OpTimes.LatestDep, OpTimes.EarliestDep)

    @staticmethod
    def InArrCurfew(t):
        if not isinstance(t, nptime):
            return False

        return TimeIsInWindow(t, OpTimes.LatestArr, OpTimes.EarliestArr)



class FleetType:
    def __init__(self, fleet_type_data):
        self.fleet_type_id = fleet_type_data['fleet_type_id']
        self.fleet_icao_code = fleet_type_data['fleet_icao_code']
        self.description = fleet_type_data['description']
        self.min_turnaround = str_to_timedelta(
            fleet_type_data['min_turnaround']
            )
        self.ops_turnaround_length = str_to_timedelta(
            fleet_type_data['ops_turnaround']
            )
        
    def __str__(self):
        return self.fleet_icao_code

class Airport:
    def __init__(self, airport_data):
        self.iata_code = airport_data['iata_code']
        self.icao_code = airport_data['icao_code']
        self.city = airport_data['city']
        self.airport_name = airport_data['airport_name']
        if airport_data['timezone'] is None:
            print(airport_data)
            exit(1)
        self.timezone = airport_data['timezone']
        if ('curfew_start' in airport_data
        and 'curfew_finish' in airport_data):
            self.curfew_start = str_to_nptime(airport_data['curfew_start'])
            self.curfew_finish = str_to_nptime(airport_data['curfew_finish'])
        else:
            self.curfew_start = self.curfew_finish = None
        
    def __str__(self):
        return "{}/{} - {}".format(
            self.iata_code, self.icao_code, self.city
            )
        
    def in_curfew(self, val):
        """check whether a time is within curfew hours"""
        if (not isinstance(val, nptime) or self.curfew_start is None
         or self.curfew_finish is None):
            return False
            
        return TimeIsInWindow(val, self.curfew_start, self.curfew_finish)

    def getRandomStartTime(self):
        retVal = None
        rnd.seed()
        while retVal is None:
            retVal = nptime(5, 30) + \
                     timedelta(seconds=rnd.randrange(0, 120) * 300)
            if self.in_curfew(retVal) or OpTimes.InDepCurfew(retVal):
                #print("Bad start time {}".format(retVal))
                retVal = None

        return retVal
        
class Flight:
    def __init__(self, flight_data):
        self.flight_number = flight_data['flight_number']
        self.isMaintenance = (self.flight_number == 'MTX')
        self.fleet_type = flight_data['fleet_type']
        self.distance_nm = flight_data['distance_nm']

        # airport info
        self.base_airport = flight_data['base_airport']
        self.dest_airport = flight_data['dest_airport']
        self.delta_tz = self.dest_airport.timezone - self.base_airport.timezone
        
        # flight and turnaround times
        self.outbound_length = str_to_timedelta(flight_data['outbound_length'])
        self.inbound_length = str_to_timedelta(flight_data['inbound_length'])
        self.turnaround_length = str_to_timedelta(flight_data['turnaround_length'])

        # sector data
        self.sectors = { "outbound" : [], "inbound" : [] }
        if 'sectors' in flight_data and len(flight_data['sectors']) > 0: 
        # flight has at least one stop
        #    for dirn in ["outbound", "inbound"]:
            for leg in flight_data['sectors']:
                self.sectors[leg['direction'] + "bound"].append({
                    "start_airport" : leg['start_airport'],
                    "end_airport" : leg['end_airport'],
                    "sector_length" : str_to_timedelta(leg['sector_length'])
                })
            self.hasStops = True
            
        else: # non-stop flight
            self.sectors["outbound"].append({
                    "start_airport" : self.base_airport,
                    "end_airport" : self.dest_airport,
                    "sector_length" : self.outbound_length})

            self.sectors["inbound"].append({
                    "start_airport" : self.dest_airport,
                    "end_airport" : self.base_airport,
                    "sector_length" : self.inbound_length})
            self.hasStops = False        

    
    def getOutbound(self):
        return (reduce(lambda x, y: x+y, 
            map(lambda x: x['sector_length'], self.sectors["outbound"])) 
            + (len(self.sectors["outbound"]) - 1) * 
              self.fleet_type.min_turnaround)

    def getInbound(self):
        return (reduce(lambda x, y: x+y, 
            map(lambda x: x['sector_length'], self.sectors["inbound"]))
            + (len(self.sectors["inbound"]) - 1) * 
                   self.fleet_type.min_turnaround)
        
    def length(self):
        """an indicative length for a full rotation, including base 
        turnaround"""
        return (self.outbound_length + self.inbound_length 
            + self.turnaround_length)
        
    def __str__(self):
        return "{}: {}-{} ({})".format(
            self.flight_number, self.base_airport.iata_code, 
            self.dest_airport.iata_code, self.fleet_type.fleet_icao_code
            )
        
    def to_dict(self):
        out = dict()
        out['flight_number'] = self.flight_number
        out['base_airport_iata'] = self.base_airport.iata_code
        out['dest_airport_iata'] = self.dest_airport.iata_code
        out['fleet_type_id'] = self.fleet_type.fleet_icao_code
        out['outbound_length'] = str(self.outbound_length)
        out['inbound_length'] = str(self.inbound_length)
        
        return out
    
    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)
    
#    def __eq__(self, a):
#        return (a is not None
#            and a.flight_number == self.flight_number
#            and a.base_airport.iata_code == self.base_airport.iata_code
#            and a.dest_airport.iata_code == self.dest_airport.iata_code
#            and a.fleet_type.fleet_type_id == self.fleet_type.fleet_type_id
#            and a.outbound_length == self.outbound_length
#            and a.inbound_length == self.inbound_length)
#        return (isinstance(a, Flight) and self.to_dict() == a.to_dict())


"""
stores details of all flights available from provided source
"""
class FlightManager:
    def __init__(self, source, build=True):
        if not isinstance(source, DataSource):
            raise Exception("No valid data source provided")
            
        self.source = source
        self.game_id = source.game_id
        self.flights = {}
        self.airports = {}
        self.fleet_types = {}
        self.MTXFlights = {}
        
        if build:
            self.getFlights()
        #print(self.flights)
        
    """
    get flight data from data source
    """
    def getFlights(self):
 
        airport_fields = [
            'dest_airport_iata', 'iata_code', 'icao_code', 'city',
            'airport_name',
            'timezone', 'curfew_start', 'curfew_finish',
        ]
        fleet_type_fields = [
            'fleet_type_id', 'description', 'min_turnaround',
            'fleet_icao_code',
            'ops_turnaround',
        ]
        flight_fields = [
            'flight_number', 'fleet_type_id', 'outbound_length',
            'inbound_length',
            'turnaround_length', 'distance_nm', 'sectors'
        ]

        self.flight_lookup = {}


        data = self.source.getBases()
       # print("bases:\n{}".format(data))

        for row in data:
            self.airports[row['iata_code']] = Airport(
                {key: value for key, value in row.items() if
                 key in airport_fields}
            )

        if len(self.airports.keys()) == 0:
            return False

        # destination airports
        data = self.source.getDestinations()
        # print("airports:\n{}".format(data))

        for row in data:
            if row['iata_code'] not in self.airports:
                self.airports[row['iata_code']] = Airport(
                    {key: value for key, value in row.items() if
                     key in airport_fields}
                )

        # fleet_types
        data = self.source.getFleets()

        # print("fleets:\n{}".format(data))

        for row in data:
            row['fleet_icao_code'] = row['icao_code']
            self.fleet_types[row['fleet_type_id']] = FleetType({
                                                       key: value
                                                       for
                                                       key, value
                                                       in
                                                       row.items()
                                                       if
                                                       key in fleet_type_fields
                                                                   })

        # flights
        data = self.source.getFlights()
        # print("flights:\n{}".format(data))

        for row in data:
            # print(row)
            base_airport_iata = row['base_airport_iata']
            fleet_type_id = row['fleet_type_id']
            flight_number = row['flight_number']

            # self.flights[row['base_airport_iata']]
            if base_airport_iata not in self.flights:
                self.flights[base_airport_iata] = {}

            # self.flights[row['base_airport_iata']][row['fleet_type_id']]
            if fleet_type_id not in self.flights[base_airport_iata]:
                self.flights[base_airport_iata][fleet_type_id] = (
                    FlightCollection(self.airports[base_airport_iata])
                )

            # replace IATA codes of sector airports with pointer to objects
            if 'sectors' in row and len(row['sectors']) > 0:
                # print(row['sectors'])
                # for dirn in ("outbound", "inbound"):
                #    for s in row['sectors'][dirn]:
                #        s['start_airport'] = self.airports[s['start_airport_iata']]
                #        s['end_airport'] = self.airports[s['end_airport_iata']]
                for s in row['sectors']:
                    s['start_airport'] = self.airports[s['start_airport_iata']]
                    s['end_airport'] = self.airports[s['end_airport_iata']]
            # get the FlightCollection for this base/fleet-type pair
            flightCln = self.flights[base_airport_iata][fleet_type_id]

            # get flight details
            f = {key: value for key, value in row.items()
                 if key in flight_fields
                 }

            f['base_airport'] = self.airports[row['base_airport_iata']]
            f['dest_airport'] = self.airports[row['dest_airport_iata']]

            f['fleet_type'] = self.fleet_types[fleet_type_id]

            # permit same flight number with different fleet_type_id
            if not flight_number in self.flight_lookup:
                self.flight_lookup[flight_number] = {}
            self.flight_lookup[flight_number][fleet_type_id] = Flight(f)
            #print(self.flight_lookup[flight_number][fleet_type_id].to_json())

            # only flights with desired fleet_type_id added to collection
            flightCln.append(self.flight_lookup[flight_number][fleet_type_id])

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

        
        
"""
standard 5-hour maitenance check; functions as a flight with destination
same as base
"""      
class MaintenanceCheckA(Flight):
    """weekly A-check of duration 5 hours"""
    def __init__(self, base_airport, fleet_type):
        self.flight_number = "MTX"
        self.isMaintenance = (self.flight_number == 'MTX')
        self.fleet_type = fleet_type
        self.distance_nm = 0

        # airport info
        self.base_airport = base_airport
        self.dest_airport = base_airport
        self.delta_tz = 0

        # flight and turnaround times
        self.outbound_length = timedelta(hours=5)
        self.inbound_length = timedelta(0, 0)
        self.turnaround_length = timedelta(0, 0)
        self.hasStops = False
        self.hasBaseTurnaround = False

    def getOutbound(self):
        return self.outbound_length

    def getInbound(self):
        return self.inbound_length


"""
container for subset of flights from FlightManager
"""
class FlightCollection:
    def __init__(self, base_airport, shuffle =True):
        self.base_airport = base_airport        
        self.shuffle = shuffle

        self.lexIndex = []
        self.durationIndex = []
        self.MTXEntry = None
        self.flights = dict()
        self.deleted = dict()
        
    def clone(self):
        out = FlightCollection(self.base_airport, self.shuffle)
        out.flights = self.flights.copy()
        out.deleted = self.deleted.copy()

        out.MTXEntry = self.MTXEntry
        out.buildDurationIndex()
        
        return out
    
       
    def append(self, f):
        if not isinstance(f, Flight) or f is None:
            raise Exception("Bad flight appended to FlightCollection")
            
        if (f.isMaintenance):
            self.MTXEntry = f

        self.flights[f.flight_number] = { 
                                          'flight' : f, 
                                          'deleted' : False,
                                          'length' : f.length()
                                        }
        self.deleted[f.flight_number] = False
        
    
    """
    eliminate entries completely, rather than mark deleted
    """

    
    """
    eliminate entries completely, rather than mark deleted
    """
    def destroyFlightNumbers(self, deletions):
        if deletions is None:
            return False
        
        try:
            iter(deletions)
            if len(deletions) == 0:
                return False
        except:
            deletions = [deletions]
            
        for k in deletions:
            try:
                del self.flights[k]
                del self.deleted[k]
            except KeyError:
                pass
            
        self.buildDurationIndex()
        
        return True

            
    """
    delete all flights exceeding specified distance in nm
    """
    def setMaxRange(self, max_range):
        if not isinstance(max_range, int) or max_range <= 0:
            return
            
        for f in self.flights:
            if self.flights[f].distance_nm > max_range:
                del self.deleted[f]
                del self.flights[f]

 
    """index of flights in descending order"""
    def buildDurationIndex(self):
        self.durationIndex = sorted(self.flights.keys(),
                                    key=lambda x: self.flights[x]['length'],
                                    reverse=True)

    """
    returns a non-deleted flight of shorter or equal total duration than 
    provided timespan
    
    if random is False (default), search is in descending order of duration
    if random is True, first shorter flight is returned
    if no shorter flight available, return None
    """
    def getShorterFlight(self, fltLength, isRandom=False, debug=False):
        if fltLength is None or not isinstance(fltLength, timedelta):
            return None
            
        vals = self.durationIndex[:]
        if isRandom:
            rnd.shuffle(vals)
        
        if debug:
            print("getShorterFlight({})".format(str(fltLength)))
            
        
        for i in vals:
            x = self.flights[i]['flight']
            if debug:
                 print("\t{} length={} deleted={}".format(x.flight_number, 
                       self.flights[i]['length'], self.deleted[i]))
            if not self.deleted[i] and self.flights[i]['length'] <= fltLength:
                if debug:
                    print("getShorterFlight: return {}".format(x.flight_number))
                return x
        #print("{}: No more valid flights".format(__name__))
        return None
    
    def delCount(self):
        return self.deleted.values().count(True)
            
        
    def delete(self, f):
#        print("-{}/".format(f.flight_number), end='')
#        if re.search('317', f.flight_number):
#            print('[@{}] '.format(f.flight_number), end='')
        self.deleted[f.flight_number] = True
        self.flights[f.flight_number]['deleted'] = True
#        print("{} ".format(list(self.deleted.values()).count(True)), end='')
        
    def undelete(self, f):
#        print("+{}/".format(f.flight_number), end='')
        self.deleted[f.flight_number] = False
        self.flights[f.flight_number]['deleted'] = False
#        print("{} ".format(list(self.deleted.values()).count(True)), end='')

    def __iter__(self):
        return FlightCollectionIter(self)
    
    def ordered(self):
        return OrderedFlightIter(self)

    def __str__(self):
        return " ".join(sorted(self.flights.keys()))
        
    def releaseMTX(self):
        if self.MTXEntry:
            self.undelete(self.MTXEntry)

    def reset(self):
        for i in self.deleted:
            self.deleted[i] = False
            self.flights[i]['deleted'] = False
            
    def __len__(self):
        return len(self.deleted) - list(self.deleted.values()).count(True)

    
    def total_time(self):
        out = timedelta(0, 0)
        for x in self.flights.values():
            if not x['deleted']:
                out += x['flight'].length()
        return out
            
    def status(self):
        available = filter(lambda x: self.deleted[x] == False, 
                         self.deleted.keys())
        deleted = filter(lambda x: self.deleted[x] == True, 
                         self.deleted.keys())
        return "Available: {}\nDeleted: {}".format(
                " ".join(sorted(available)), " ".join(sorted(deleted))
                )

    def setShuffle(self, status):
        self.shuffle = status
                
"""
iterator for all flights in a FlightCollection
"""       
class FlightCollectionIter:
    def __init__(self, flightCollection):
        """add the indexes of all non-deleted flights"""
        self.pos = 0
        self.available = []
        self.coll = flightCollection
#        print("### new FlightCollectionIter {}/{}".format(
#                list(self.coll.deleted.values()).count(True),
#                list(filter(lambda x: self.coll.deleted[x], 
#                            self.coll.deleted))))
        self.available = list(filter(lambda k: not self.coll.deleted[k], 
                                self.coll.deleted))
        
        # shuffle to make it interesting
        if self.coll.shuffle:
            rnd.shuffle(self.available)
        
    def __iter__(self):
        return self

    def __next__(self):
        if self.pos < len(self.available):
            retVal = self.coll.flights[self.available[self.pos]]['flight']
            self.pos += 1
            return retVal
        else:
            raise StopIteration()        





"""
iterator for all flights in a FlightCollection in duration order
"""       
class OrderedFlightIter:
    def __init__(self, flightCollection):
        """add the indexes of all non-deleted flights"""
        self.pos = 0
        self.available = []
        self.coll = flightCollection
        self.available = list(filter(lambda k: not self.coll.deleted[k], 
                                self.coll.durationIndex))

        
    def __iter__(self):
        return self

    def __next__(self):
        if self.pos < len(self.available):
            retVal = self.coll.flights[self.available[self.pos]]['flight']
            self.pos += 1
            return retVal
        else:
            raise StopIteration()        