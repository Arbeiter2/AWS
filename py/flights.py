from datetime import timedelta
from nptime import nptime
from nptools import str_to_timedelta, str_to_nptime, TimeIsInWindow
from copy import deepcopy
import random
from functools import reduce


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
            + (len(self.sectors["outbound"]) - 1) * self.fleet_type.min_turnaround)

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
    def __init__(self, shuffle =True):
        self.shuffle = shuffle
        self.flights = []
        self.deleted = []
        self.MTXEntry = None
        
    def append(self, f):
        if not isinstance(f, Flight):
            raise Exception("Bad flight appended to FlightCollection")
            
        self.flights.append(f)
        self.deleted.append(False)
        if (f.isMaintenance):
            self.MTXEntry = f

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
            
    def __len__(self):
        length = 0
        for x in range(0, len(self.flights)):
            if not self.deleted[x]:
                length += 1
        return length
    
    def total_time(self):
        out = timedelta(0, 0)
        for x in range(0, len(self.flights)):
            if not self.deleted[x]:
                out += (self.flights[x].outbound_length + 
                2 * self.flights[x].turnaround_length + 
                self.flights[x].inbound_length) 
        return out
            
    def status(self):
        available = []
        deleted = []
        for i in range(0, len(self.flights)):
            if self.deleted[i]:
                deleted.append(self.flights[i].flight_number)
            else:
                available.append(self.flights[i].flight_number)
        
        return "Available: {}\nDeleted: {}".format(
                " ".join(available), " ".join(deleted)
                )
                
        
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
