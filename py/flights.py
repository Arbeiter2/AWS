from datetime import timedelta
from nptime import nptime
from nptools import str_to_timedelta, str_to_nptime, TimeIsInWindow
from datasources import DataSource
import random
from functools import reduce
import bitstring


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
            + (len(self.sectors["inbound"]) - 1) * self.fleet_type.min_turnaround)
        
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

class FlightManager:
    def __init__(self, source):
        if not isinstance(source, DataSource):
            raise Exception("No valid data source provided")
            
        self.source = source
        self.game_id = source.game_id
        self.flights = {}
        self.airports = {}
        self.fleet_types = {}
        self.MTXFlights = {}
        
        self.getFlights()
        print(self.flights)
        
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
        
class FlightCollection:
    def __init__(self, base_airport, shuffle =True):
        self.base_airport = base_airport        
        self.shuffle = shuffle
        self.flights = [None] # location 0 reserved for MTX
        self.deleted = [False] # location 0 reserved for MTX
        self.indexMap = dict()
        self.indexMap['MTX'] = 0
        self.durationIndex = []
        self.MTXEntry = None
        
    def append(self, f):
        if not isinstance(f, Flight) or f is None:
            raise Exception("Bad flight appended to FlightCollection")
            
        if (f.isMaintenance):
            self.MTXEntry = f
            self.flights[0] = f
        else:
            self.flights.append(f)
            self.deleted.append(False)
            self.indexMap[f.flight_number] = len(self.flights) - 1

    def buildDurationIndex(self):
        """index of flights in descending order"""
        self.durationIndex = sorted(range(len(self.flights)),
                                    key=lambda x: self.flights[x].length,
                                    reverse=True)
        
    def getShorterFlight(self, fltLength, random=False):
        if fltLength is None or not isinstance(fltLength, timedelta):
            return None
            
        if random:
            vals = range(0, len(self.flights))
        else:
            vals = self.durationIndex
        
        for i in vals:
            if not self.deleted[i] and self.flights[i].length <= fltLength:
                return self.flights[i]
            
        return None
            
        
    def deleteByFlightNumber(self, flight_number):
        for f in self.flights:
            if f.flight_number == flight_number:
                self.setDeletedState(f, True) 
            
    def delete(self, f):
        self.setDeletedState(f, True)
        
    def undelete(self, f):
        self.setDeletedState(f, False)

    def setDeletedState(self, f, state):
        if f not in self.flights:
            return
            
        self.deleted[self.flights.index(f)] = state
        
    def __iter__(self):
        return FlightCollectionIter(self)

    def __str__(self):
        out = ""
        for f in self.flights:
            out = out + f.flight_number + "\n"
        return out
        
    def releaseMTX(self):
        if self.MTXEntry:
            self.undelete(self.MTXEntry)

    def reset(self):
        for i in range(0, len(self.deleted)):
            self.deleted[i] = False
            
    def getIndex(self, flight_number):
        return self.indexMap.get(flight_number)
            
    def __getitem__(self, key):
        if key in range(0, len(self.flights)):
            return self.flights[key]
        else:
            return None
            
    def __len__(self):
        length = 0
        for x in range(0, len(self.flights)):
            if not self.deleted[x]:
                length += 1
        return length
    
    def total_time(self):
        out = timedelta(0, 0)
        for x in range(1, len(self.flights)):
            if not self.deleted[x]:
                out += (self.flights[x].outbound_length + 
                2 * self.flights[x].turnaround_length + 
                self.flights[x].inbound_length) 
        return out
        
    def toBitstring(self):
        return ~(bitstring.Bits(self.deleted))
            
    def status(self):
        available = []
        deleted = []
        for i in range(1, len(self.flights)):
            if self.deleted[i]:
                deleted.append(self.flights[i].flight_number)
            else:
                available.append(self.flights[i].flight_number)
        
        return "Available: {}\nDeleted: {}".format(
                " ".join(available), " ".join(deleted)
                )
                
    def setShuffle(self, status):
        self.shuffle = status
                
        
class FlightCollectionIter:
    def __init__(self, flightCollection):
        """add the indexes of all non-deleted flights"""
        self.pos = 0
        self.available = []
        self.coll = flightCollection
        for i in range(0, len(self.coll.deleted)):
            if not self.coll.deleted[i]:
                self.available.append(i)
        
        # shuffle to make it interesting
        if self.coll.shuffle:
            random.shuffle(self.available)
        
    def __iter__(self):
        return self
        
    def __next__(self):
        if self.pos < len(self.available):
            retVal = self.coll.flights[self.available[self.pos]]
            self.pos += 1
            return retVal
        else:
            raise StopIteration()
