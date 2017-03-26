from flights import (Airport, Flight, FleetType, FlightCollection,
                     FlightManager, OpTimes)
from datetime import timedelta
from nptime import nptime
from nptools import (str_to_timedelta, str_to_nptime, TimeIsInWindow, 
                     nptime_diff_sec, time_to_str)
import re
from datasources import DataSource
from collections import OrderedDict
import itertools
from functools import reduce
import copy
import random as rnd
import pdb
import json
import math




"""
container representing a scheduled event in a timetable
"""
class TimetableEntry:
    def __init__(self, f, tt, post_padding = "0:00",
        dest_turnaround_padding = None):
        if not f.isMaintenance and (not isinstance(f, Flight)
        or not isinstance(tt, Timetable)
        or f.base_airport.iata_code != tt.base_airport.iata_code
        or f.fleet_type.fleet_type_id != tt.fleet_type.fleet_type_id):
            print(f.base_airport,tt.base_airport,
                  f.fleet_type,tt.fleet_type)
            raise Exception("Invalid flight {} \nor invalid timetable {}"
                            "passed to Timetable.ctor".format(f.to_json(), 
                                                              tt.to_dict()))

        self.flight = f
        self.parent = tt
        self.start_day = self.parent.next_start_day
        self.outbound_dep = self.parent.available_time

        # if we are loading data from the database, we want to use the
        # turnaround_length specified, otherwise use the fleet type default
        if dest_turnaround_padding is None:
            self.dest_turnaround_padding = tt.fleet_type.ops_turnaround_length
        else:
            self.dest_turnaround_padding = str_to_timedelta(
                dest_turnaround_padding
                )

        # maintenance entries require turnaround time, but we can ignore that
        if self.flight.isMaintenance:
            self.dest_turnaround_padding = str_to_timedelta("00:00")
            self.base_turnaround_length = self.dest_turnaround_padding
            if self.flight.hasBaseTurnaround:
                self.post_padding = tt.fleet_type.min_turnaround
            else:
                self.post_padding = str_to_timedelta(post_padding)
        else:
            self.base_turnaround_length = self.parent.base_turnaround_length
            self.post_padding = str_to_timedelta(post_padding)

        self.max_padding = self.flight.turnaround_length * 2.0
        self.metaScore = FlightScore(self)

        self.recalc()
        #self.adjust()

    def clone(self):
        return TimetableEntry(self.flight, self.parent, self.post_padding,
                                  self.dest_turnaround_padding)


    def recalc(self):
        self.outbound_arr = (self.outbound_dep + self.flight.getOutbound() +
            timedelta(seconds=int(self.flight.delta_tz * 3600)))
        self.inbound_dep = self.outbound_arr + self.dest_turnaround_padding
        self.inbound_arr = (self.inbound_dep + self.flight.getInbound() +
            timedelta(seconds=-int(self.flight.delta_tz * 3600)))
        self.available_time = (self.inbound_arr + self.base_turnaround_length +
            self.post_padding)
#        print("id:{} fl:{} tu:{} {} {} {} {} {}".format(self.parent.timetable_id,
#              self.flight.flight_number,
#              self.dest_turnaround_padding,
#              self.outbound_dep, self.outbound_arr,
#              self.inbound_dep, self.inbound_arr,
#              self.available_time))


        self.total_time = (self.flight.getOutbound() +
            self.dest_turnaround_padding + self.flight.getInbound() +
            self.base_turnaround_length + self.post_padding)
        self.available_day = self.start_day + int(
            self.outbound_dep.to_timedelta().seconds +
            self.total_time.total_seconds()) // 86400

        # correct for days going over a weekend
        if (self.available_day > 7):
            self.available_day = self.available_day % 7

        self.scoreCalc()

    def scoreCalc(self):
        self.metaScore.calc()


    def is_good(self):
        #self.score()
        return self.metaScore.get() == 0

    def getLength(self):
        return self.total_time
#==============================================================================
#         return (self.flight.length() + 
#                 self.dest_turnaround_padding +
#                 self.parent.fleet_type.ops_turnaround_length +
#                 self.post_padding)
# 
#==============================================================================
    def checkLegCurfews(self):
        # check whether any legs are in breach of curfew at the tech stop
        #print ("Checking curfews for {}".format(self.flight.__str__()))
        out = []
        for dirn in ("outbound", "inbound"):
            if dirn == "outbound":
                start = self.outbound_dep
            else:
                start = self.inbound_dep

            # we don't need to check arrival at the last point, as this
            # covered in the standard is_good check
            for i in range(0, len(self.flight.sectors[dirn])-1):
                leg = self.flight.sectors[dirn][i]
                delta_tz = (leg['end_airport'].timezone -
                    leg['start_airport'].timezone)

                arr = (start + leg['sector_length'] + timedelta(
                    seconds=int(delta_tz * 3600)))

                dep = arr + self.flight.fleet_type.min_turnaround
                #print("{} - {}: arr/{} dep/{}".format(leg['start_airport'].iata_code, leg['end_airport'].iata_code, arr, dep))

                if leg['end_airport'].in_curfew(arr):
                    out.append("{} closed at arrival time {}".format(
                        leg['end_airport'].iata_code, arr))

                if leg['end_airport'].in_curfew(dep):
                    out.append("{} closed at departure time {}".format(
                        leg['end_airport'].iata_code, dep))

                # ready for the next hop, where this becomes the start_airport
                start = dep

        return out

    """
    modify dest_turnaround_padding and/or base_turnaround_padding to improve
    score, ensuring parent timetable does not exceed permissible hours
    """
    def adjust(self):
        # do nothing if we're healthy already
        if self.metaScore.get() == 0.0:
            return

        # maximum adjustment possible, based on parent
        max_adjust = self.parent.remaining()

        #
        # adjust dest_turnaround_padding
        #

        # find the effective inbound curfew
        inbound_curfew_start = OpTimes.LatestDep
        inbound_curfew_finish = OpTimes.EarliestDep

        # if destination airport has curfew, use that instead
        if self.flight.dest_airport.curfew_start is not None:
            # e.g. curfew_start == 23:00, LatestDep == 00:30
            if (self.flight.dest_airport.curfew_start - OpTimes.LatestDep >
                    timedelta(hours=12)):
                inbound_curfew_start = self.flight.dest_airport.curfew_start

            if self.flight.dest_airport.curfew_finish > OpTimes.EarliestDep:
                inbound_curfew_finish = self.flight.dest_airport.curfew_finish


        # if the end of the curfew is not too far away, add some padding to
        # the destination turnaround
        if TimeIsInWindow(self.inbound_dep, inbound_curfew_start,
            inbound_curfew_finish):
            delta = timedelta(seconds=(
                inbound_curfew_finish -
                self.inbound_dep +
                timedelta(seconds=300)).seconds)
            if delta < min([max_adjust, self.max_padding]):
                #pass
                self.dest_turnaround_padding += delta
                #print("Padding inbd {} from {} to {} ({})".format(
                 #   str(self.flight), stt,
                  #  self.inbound_dep + delta,
                  #  self.dest_turnaround_padding))
                self.recalc()
                self.parent.recalc()
                if self.metaScore.get() == 0.0:
                    return


        #
        # adjust post_padding
        #
        max_adjust = self.parent.remaining()

        # find the effective curfew for the next flight after this one
        outbound_curfew_start = OpTimes.LatestDep
        outbound_curfew_finish = OpTimes.EarliestDep

        if self.flight.base_airport.curfew_start is not None:
            if (self.flight.base_airport.curfew_start - OpTimes.LatestDep >
                    timedelta(hours=12)):
                outbound_curfew_start = self.flight.base_airport.curfew_start

            if self.flight.base_airport.curfew_finish > OpTimes.EarliestDep:
                outbound_curfew_finish = self.flight.base_airport.curfew_finish

        # if the end of the curfew is not too far away, add some padding to
        # the base turnaround
        if TimeIsInWindow(self.available_time, outbound_curfew_start,
            outbound_curfew_finish):
            delta = timedelta(seconds=(
                outbound_curfew_finish -
                self.available_time +
                timedelta(seconds=300)).seconds)
            if delta < min([max_adjust, self.max_padding]):
                self.post_padding += delta
                #print("Padding inbd {} from {} to {}".format(
                #   str(self.flight), stt, self.base_turnaround_length))

                self.recalc()


    def __str__(self):
        return (
            "{:<8}"      # flight_number
            "{:<6}"      # dest airport
            "{:<8}"      # distance_nm
            "{:<5}"      # start day
            "{:<10}"     # outbound_dep
            "{:<10}"     # outbound_arr
            "{:<10}"     # inbound_dep
            "{:<10}"     # inbound_arr
            "{:<18}"     # total time
            "{:<5}"      # available_day
            "{:<10}\n"   # available time
            .format(
                str(self.flight.flight_number),
                self.flight.dest_airport.iata_code,
                self.flight.distance_nm,
                self.start_day, self.outbound_dep.strftime("%H:%M"),
                self.outbound_arr.strftime("%H:%M"),
                self.inbound_dep.strftime("%H:%M"),
                self.inbound_arr.strftime("%H:%M"), 
                str(self.total_time),
                self.available_day, self.available_time.strftime("%H:%M")))

    def to_dict(self):
        out = OrderedDict()
        out['timetable_id'] = self.parent.timetable_id
        out['flight_number'] = self.flight.flight_number
        out['dest_airport_iata'] = self.flight.dest_airport.iata_code
        out['start_day'] = self.start_day
        out['start_time'] = time_to_str(self.outbound_dep)
        out['outbound_arr'] = time_to_str(self.outbound_arr)
        if (self.dest_turnaround_padding >
            self.parent.fleet_type.ops_turnaround_length):
            out['dest_turnaround_padding'] = time_to_str(
                self.dest_turnaround_padding -
                self.parent.fleet_type.ops_turnaround_length)
        else:
            out['dest_turnaround_padding'] = "00:00"

        out['inbound_dep'] = time_to_str(self.inbound_dep)
        out['inbound_arr'] = time_to_str(self.inbound_arr)
        out['earliest_available'] = time_to_str(self.available_time)
        out['post_padding'] = time_to_str(self.post_padding)

        return out

"""
fitness measure of TimetableEntry across multiple parameters

an entry with no problems has a score of zero (0) for all parameters
"""
class FlightScore:
    def __init__(self, entry):
        self.errors = dict()
        self.reset()
        if not isinstance(entry, TimetableEntry):
            raise Exception("FlightScore.__init__: "
                            "Invalid TimetableEntry [{}]".format(entry))
        self.ttEntry = entry

    def reset(self):
        self.errors['outbound_dep_graveyard'] = 0
        self.errors['outbound_dep_curfew'] = 0
        self.errors['outbound_arr_graveyard'] = 0
        self.errors['outbound_arr_curfew'] = 0

        self.errors['inbound_dep_graveyard'] = 0
        self.errors['inbound_dep_curfew'] = 0
        self.errors['inbound_arr_graveyard'] = 0
        self.errors['inbound_arr_curfew'] = 0

        self.errors['distance'] = 0
        self.errors['leg_curfews'] = 0
        self.errors['conflicts'] = 0

    def calc(self):
        self.reset()
        
#        if self.ttEntry.flight.isMaintenance:
#            print("Scoring MTX")

        # reject flights exceeding maximum range of timetable
        if (self.ttEntry.parent.max_range is not None
        and self.ttEntry.distance_nm > self.ttEntry.parent.max_range):
            self.errors['distance'] = 1

        # check airport curfews first
        parent = self.ttEntry.parent
        flight = self.ttEntry.flight
        if parent.base_airport.in_curfew(self.ttEntry.outbound_dep):
            self.errors['outbound_dep_curfew'] = 2
        if flight.dest_airport.in_curfew(self.ttEntry.outbound_arr):
            self.errors['outbound_arr_curfew'] = 2
        if flight.dest_airport.in_curfew(self.ttEntry.inbound_dep):
            self.errors['inbound_dep_curfew'] = 2
        if parent.base_airport.in_curfew(self.ttEntry.inbound_arr):
            self.errors['inbound_arr_curfew'] = 2

        # check operation curfews next
        if not flight.isMaintenance and not parent.graveyard:
            if OpTimes.InDepCurfew(self.ttEntry.outbound_dep):
                self.errors['outbound_dep_graveyard'] = 1
            if OpTimes.InArrCurfew(self.ttEntry.outbound_arr):
                self.errors['outbound_arr_graveyard'] = 1
            if OpTimes.InDepCurfew(self.ttEntry.inbound_dep):
                self.errors['inbound_dep_graveyard'] = 1
            if OpTimes.InArrCurfew(self.ttEntry.inbound_arr):
                self.errors['inbound_arr_graveyard'] = 1

        # check individual legs for curfew violations
        if flight.hasStops:
            res = self.ttEntry.checkLegCurfews()
            self.errors['leg_curfews'] = len(res) * 2

        # look for conflicts with other flights on the same route
        if (parent.ttManager
        and parent.ttManager.hasConflicts(self.ttEntry)):
            self.errors['conflicts'] = 1
            
    def curfewError(self):
        return (self.errors['outbound_dep_curfew'] != 0
             or self.errors['outbound_arr_curfew'] != 0
             or self.errors['inbound_dep_curfew'] != 0
             or self.errors['inbound_arr_curfew'] != 0)

    def get(self):
        return math.sqrt(sum(map(lambda x: x * x, self.errors.values())))


"""
container representing aircraft timetable

consists of an ordered collection of TimetableEntry objects
"""
class Timetable:

    def __init__(self, ttManager, # parent TimetableManager
                 game_id=None,
                 timetable_id=None,
                 timetable_name=None, 
                 base_airport =None, 
                 fleet_type=None,
                 outbound_dep=None, 
                 base_turnaround_delta=None,
                 max_range=None, 
                 graveyard=True):

        if (not isinstance(ttManager, TimetableManager)
        or  not isinstance(base_airport, Airport)
        or  not isinstance(fleet_type, FleetType)
        or  not isinstance(str_to_nptime(outbound_dep), nptime)):
            print("##P{} {} {} {}".format(str(ttManager), str(base_airport),
                  str(fleet_type), outbound_dep))
            raise Exception("Timetable(): Invalid args")

        self.ttManager = ttManager

        self.flights = []
        self.game_id = game_id
        self.timetable_name = timetable_name
        self.base_airport = base_airport
        self.fleet_type = fleet_type
        self.timetable_id = timetable_id
        self.graveyard = graveyard
        self.iterPos = 0            # iterator position

        # by convention
        self.next_start_day = 1
        self.start_time = str_to_nptime(outbound_dep)
        self.available_time = str_to_nptime(outbound_dep)

        # if base_turnaround_delta is supplied, add it to base turnaround, and
        # if it is greater than or comparable to the ops_turnaround value,
        # use the new sum as the base_turnaround_length
        #
        # otherwise, use the ops_turnaround as base_turnaround_length
        #
        delta = str_to_timedelta(base_turnaround_delta)
        if (delta is not None
        and delta + self.fleet_type.min_turnaround >=
                self.fleet_type.ops_turnaround_length):
            self.base_turnaround_length =delta + self.fleet_type.min_turnaround
            self.base_turnaround_delta = delta
        else:
            self.base_turnaround_length = self.fleet_type.ops_turnaround_length
            self.base_turnaround_delta = (
                    self.fleet_type.ops_turnaround_length -
                    self.fleet_type.min_turnaround
                    )

        self.max_range = None
        if max_range is not None and max_range > 0:
            self.max_range = max_range
            
        self.aggTime = timedelta(0,0)
        
    """
    check whether a flight is in a timetable
    
    can handle either a string or a FLight object
    """
    def contains(self, f):
        if len(self.flights) == 0:
            return False
        
        if isinstance(f, Flight):
            return any(e.flight is f for e in self.flights)
        
        if isinstance(f, str):
            return any(e.flight.flight_number == f for e in self.flights)
        return False

    

    def clone(self):
        newTT = Timetable(self.ttManager,
            game_id=self.game_id,
            timetable_id=self.timetable_id,
            timetable_name=self.timetable_name,
            base_airport=self.base_airport,
            fleet_type=self.fleet_type,
            outbound_dep=self.outbound_dep,
            base_turnaround_delta=self.base_turnaround_delta,
            graveyard=self.graveyard,
            max_range=self.max_range)

        newTT.flights = [e.clone() for e in self.flights]

    """
    create a random timetable from available flights, starting with MTX,
    then permute
    """
    def randomise(self, fltCln):
        if not isinstance(fltCln, FlightCollection):
            return False
        
        self.flights = []

        mtx = (
                self.ttManager.fMgr.MTXFlights[self.base_airport.iata_code]
                [self.fleet_type.fleet_type_id]
                )
        self.append(TimetableEntry(mtx, self))
        self.recalc()

        # randomly choose available flights until nothing else can be added
        while True:
            newFlight = fltCln.getShorterFlight(self.remaining(), True)
            print("randomise {}".format(newFlight))
            if newFlight is None:
                break
            else:
                fltCln.delete(newFlight)
                self.appendFlight(newFlight)
                self.recalc()
            print(self)

        # permute order
        self.flights = list(list(itertools.permutations(self.flights))[
                rnd.randint(1, math.factorial(len(self.flights)))
                ])
        self.recalc()
        
        return self


    def appendFlight(self, f):
        if (not isinstance(f, Flight)
        or f.base_airport != self.base_airport
        or (not f.isMaintenance
            and f.fleet_type != self.fleet_type)):
            raise Exception("Invalid flight "
                            "passed to Timetable.appendFlight: {}".format(f))

        newEntry = TimetableEntry(f, self)
        return self.append(newEntry)


    """add TimetableEntry"""
    def append(self, f):
        # throw exception for invalid  arg
        if (not isinstance(f, TimetableEntry)
        or f.flight.base_airport.iata_code != self.base_airport.iata_code
        or (not f.flight.isMaintenance
            and f.flight.fleet_type.fleet_type_id != 
                self.fleet_type.fleet_type_id)):
            raise Exception("Invalid flight "
                            "passed to Timetable.append: {}".format(f))

        # check total length
        if f.getLength() > self.remaining():
            return False

        # check whether this flight is already in the timetable
        for x in self.flights:
            if x == f or x.flight.flight_number == f.flight.flight_number:
                # don't raise an exception, just do nothing
                # raise Exception("Flight [{}] already in timetable".
                # format(x.flight.flight_number))
                return False

        self.flights.append(f)

        self.next_start_day = f.available_day
        self.available_time = f.available_time
        self.recalc()

        return True

    def __add__(self, f):
        out = copy.copy(self)
        out.flights = copy.copy(self.flights)
        out.append(f)

        return out

    def __str__(self):
        out = "[\n"
        for e in self.flights:
            out += str(e)
        return (out + "]\nNext start day: {}; "
                        "Next available: {}; "
                        "Total time: {}".format(self.next_start_day,
                                     self.available_time, self.total_time())
            )

    def lex(self):
        """return ordered comma-separated list of flights in this timetable"""
        return ",".join(sorted(map(lambda x: x.flight.flight_number,
                                   self.flights)))

    """return comma-separated list of flights in this timetable"""
    def seq(self):
        return ",".join(map(lambda x: x.flight.flight_number, self.flights))

    """return a full json representation of timetable as shown below
	  {
    		"game_id": "162",
    		"timetable_id": "42",
    		"base_airport_iata": "SCL",
    		"fleet_type_id": "o8",
    		"timetable_name": "CC-MAA",
    		"fleet_type" : "A330/A340",
    		"base_turnaround_delta": "00:45",
    
    		"entries" :
    		[
    			{
    				"flight_number": "QV405",
    				"start": "09:10",
    				"earliest": "21:45",
    				"padding": "00:00",
    				"dest": "LIM",
    				"day": 1
    			},
    			
    			{
    				"flight_number": "QV489",
    				"start": "21:15",
    				"earliest": "09:10",
    				"padding": "00:00",
    				"dest": MAN",
    				"day": 1
    			},
    			...
    		]
    	}
    """
    def to_dict(self):
        out = OrderedDict()
        out["game_id"] = self.game_id
        out["timetable_id"] = self.timetable_id
        out["base_airport_iata"] = self.base_airport.iata_code
        out["fleet_type_id"] = self.fleet_type.fleet_type_id
        out["timetable_name"] = self.timetable_name
        out["fleet_type"] = self.fleet_type.description
        #out["base_turnaround_delta"] = time_to_str(
        #    self.base_turnaround_delta + self.fleet_type.min_turnaround)
        out["base_turnaround_delta"] = time_to_str(
            self.base_turnaround_delta)

        out["entries"] = list(map(lambda z: z.to_dict(), self.flights))
        #out.entries = self.flights

        return out

    def to_list(self):
        return [e.flight.flight_number for e in self.flights]

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)

    def isEmpty(self):
        return len(self.flights) == 0

    """find aggregate utilisation (ish)"""
    def total_time(self):
#        r= reduce(lambda a, x: a + x.getLength(),
#                      self.flights, timedelta(0,0))
#        print(r)
        return self.aggTime

    """available time left in the week"""
    def remaining(self):
        return (timedelta(days=7)
                - self.total_time()
                - self.base_turnaround_length)

    def hasMaintenance(self):
        for entry in self.flights:
            if entry.flight.isMaintenance:
                return True

        return False

    def recalc(self):
        self.aggTime = timedelta(0,0)

        if len(self.flights) == 0:
            return

        last_start_time = self.start_time
        self.flights[0].start_day = last_start_day = 1
        for entry in self.flights:
            entry.outbound_dep = last_start_time
            entry.start_day = last_start_day
            entry.recalc()
            last_start_time = self.available_time = entry.available_time
            self.next_start_day = last_start_day = entry.available_day
            
            self.aggTime = self.aggTime + entry.getLength()

    """check how close total is to 168 hours, and whether we have MTX"""
    def is_good(self, threshold):
        #print("ratio = {:.2}%".format(self.total_time().total_seconds()/(7 * 86400) * 100.0))
        if (self.total_time().total_seconds()/(7 * 86400) < threshold):
            return False

        if (self.total_time().total_seconds() > (7 * 86400)):
            return False

        return self.hasMaintenance()

    def getMetaData(self):
        return [f.metaScore.get() for f in self.flights]

    def getScore(self):
        return sum(self.getMetaData())



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
           
        self.game_id = self.source.game_id        
        self.routes = {}
        self.timetables = {}
        
        if build:        
            self.getTimetables()

        

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
    set MTX flight for specific base/fleet to use post_padding gap
    """
    def setMTXGapStatus(self, base_airport_iata, fleet_type_id, status):
        if (base_airport_iata not in self.fMgr.flights 
         or fleet_type_id not in self.fMgr.flights[base_airport_iata]):
            return

        mtx = self.fMgr.MTXFlights[base_airport_iata][fleet_type_id]
        mtx.hasBaseTurnaround = status

        
        
    """
    create FlightCollection for given base/fleet pair
    """
    def getFlightCollection(self, base_airport_iata, fleet_type_id,
                            exclude_flights=None, max_range=None,
                            ignore_existing=True):
        if (base_airport_iata not in self.fMgr.flights 
         or fleet_type_id not in self.fMgr.flights[base_airport_iata]):
            return None
        
        fltCln = self.fMgr.flights[base_airport_iata][fleet_type_id].clone()
        
        deletions = set()

        # a single flight number may be operated by multiple fleet_types;
        # remove all timetabled flights in other fleet_type_id values
        if not ignore_existing and base_airport_iata in self.timetables.keys():
            flTypes = filter(lambda q: q != fleet_type_id,
                             self.timetables[base_airport_iata].keys())
            for f in flTypes:
                for x in self.timetables[base_airport_iata][f]:
                    for e in x.flights:
                        if e.flight.flight_number != "MTX":
                            # print("Deleting "+str(e.flight))
                            deletions.add(e.flight.flight_number)
        
        # if ignore_existing is not set, we remove timetabled
        # flights from fltCln
        if (not ignore_existing
            and base_airport_iata in self.timetables
            and fleet_type_id in self.timetables[base_airport_iata]):
            for ttObj in self.timetables[base_airport_iata][fleet_type_id]:
                for ttEntryObj in ttObj.flights:
                    deletions.add(ttEntryObj.flight.flight_number)
            

        # if list of excluded flight numbers is supplied, delete them from
        # the FlightCollection
        if isinstance(exclude_flights, list):
            exclude_flights = [s.upper() for s in exclude_flights]
            for x in exclude_flights:
                if isinstance(x, str) and x != 'MTX':
                    deletions.add(x)
                    
        # set max range if supplied
        if isinstance(max_range, int) and max_range > 0:
            for f in fltCln.flights:
                if f.distance_nm > max_range:
                    deletions.add(f.flight_number)
                    
        fltCln.destroyFlightNumbers(deletions)
        
        #print(fltCln.deleted)
                    
                    
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
    def hasConflicts(self, ttEntry, ignore_base_timetables=False):
        debug = False
        if not isinstance(ttEntry, TimetableEntry):
            raise Exception("Bad arg passed to TimetableManager.hasConflicts")

        # maintenance cannot have conflicts; there can be only one
        if ttEntry.flight.isMaintenance:
            return False        

        # check timetables from this base if ignore_base_timetables not set
        if not ignore_base_timetables:
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