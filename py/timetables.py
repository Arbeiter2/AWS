from flights import Airport, Flight, FleetType, FlightManager
#import TimetableManager
from datetime import timedelta
from nptime import nptime
from nptools import str_to_timedelta, str_to_nptime, TimeIsInWindow, time_to_str
from TimetableManager import TimetableManager
from collections import OrderedDict
import itertools
from functools import reduce
import copy
import random as rnd
import pdb
import json
import math


        
        

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

        
    
class TimetableEntry:
    """"""
    def __init__(self, f, tt, post_padding = "0:00", 
        dest_turnaround_padding = None):
        if (not isinstance(f, Flight) 
        or not isinstance(tt, Timetable) 
        or f.base_airport != tt.base_airport 
        or not f.isMaintenance
        or f.fleet_type != tt.fleet_type):
            raise Exception("Invalid flight {} \nor invalid timetable {}"
                            "passed to Timetable.ctor".format(f, tt))

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
        return self.flight.length() + self.post_padding
            
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
        
    def adjust(self):
        # do nothing if we're healthy already
        if self.metaScore.get() == 0.0:
            return
            
        # find the effective inbound curfew
        inbound_curfew_start = OpTimes.LatestDep
        inbound_curfew_finish = OpTimes.EarliestDep

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
            if delta < self.max_padding:
                #pass
                self.dest_turnaround_padding += delta
                #print("Padding inbd {} from {} to {} ({})".format(
                 #   str(self.flight), stt, 
                  #  self.inbound_dep + delta,
                  #  self.dest_turnaround_padding))
        self.recalc()

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
            if (delta < self.base_turnaround_length * 2.0): # timedelta(seconds=5400):
                self.post_padding += timedelta(seconds=delta.seconds)
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
                self.inbound_arr.strftime("%H:%M"), str(self.total_time), 
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
        
        # reject flights exceeding maximum range of timetable
        if (self.ttEntry.parent.max_range is not None
        and self.ttEntry.distance_nm > self.ttEntry.parent.max_range):
            self.errors['distance'] = 1

        # check airport curfews first
        if self.ttEntry.base_airport.in_curfew(self.ttEntry.outbound_dep): 
            self.errors['outbound_dep_curfew'] = 2
        if self.ttEntry.dest_airport.in_curfew(self.ttEntry.outbound_arr):
            self.errors['outbound_arr_curfew'] = 2
        if self.ttEntry.dest_airport.in_curfew(self.ttEntry.inbound_dep):
            self.errors['inbound_dep_curfew'] = 2
        if self.ttEntry.base_airport.in_curfew(self.ttEntry.inbound_arr):
            self.errors['inbound_arr_curfew'] = 2

        # check operation curfews next
        if not self.ttEntry.parent.graveyard:
            if OpTimes.InDepCurfew(self.ttEntry.outbound_dep):
                self.errors['outbound_dep_graveyard'] = 1
            if OpTimes.InArrCurfew(self.ttEntry.outbound_arr):
                self.errors['outbound_arr_graveyard'] = 1
            if OpTimes.InDepCurfew(self.ttEntry.inbound_dep):
                self.errors['inbound_dep_graveyard'] = 1
            if OpTimes.InArrCurfew(self.ttEntry.inbound_arr):
                self.errors['inbound_arr_graveyard'] = 1
            
        # check individual legs for curfew violations
        if self.ttEntry.hasStops:
            res = self.ttEntry.checkLegCurfews()
            self.errors['leg_curfews'] = len(res) * 2
            
        # look for conflicts with other flights on the same route
        if (self.ttEntry.parent.flight_manager 
        and self.ttEntry.parent.flight_manager.hasConflicts(self.ttEntry)):
            self.errors['conflicts'] = 1
            
    def get(self):
        return math.sqrt(sum(map(lambda x: x * x, self.errors.values())))


 
class Timetable:
    """"""
    def __init__(self, timetable_id =None, game_id =None, timetable_name=None,
        base_airport =None, fleet_type=None, outbound_dep=None, fManager=None, 
        base_turnaround_delta =None, max_range =None, graveyard=True):
        
        if (game_id is None 
        or  not isinstance(base_airport, Airport) 
        or  not isinstance(fleet_type, FleetType)
        or  not isinstance(str_to_nptime(outbound_dep), nptime)):
            print("##P{} {} {} {}".format(game_id, str(base_airport), 
                  str(fleet_type), outbound_dep))
            raise Exception("Timetable(): Invalid args")
            
        self.flights = []
        self.game_id = game_id
        self.timetable_name = timetable_name
        self.base_airport = base_airport
        self.fleet_type = fleet_type
        self.timetable_id = timetable_id
        self.graveyard = graveyard

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
            
        
        #print(self.base_turnaround_delta)        
        # optional
        self.flight_manager = None
        if fManager and isinstance(fManager, FlightManager):
            self.flight_manager = fManager
            
        self.max_range = None
        if max_range is not None and max_range > 0:
            self.max_range = max_range
    
    def clone(self):
        newTT = Timetable(timetable_id=self.timetable_id,
            game_id=self.game_id,
            timetable_name=self.timetable_name,
            base_airport=self.base_airport,
            fleet_type=self.fleet_type,
            outbound_dep=self.outbound_dep,
            fManager=self.fManager,
            base_turnaround_delta=self.base_turnaround_delta,
            max_range=self.max_range,
            graveyard=self.graveyard,
            flight_manager=self.flight_manager,
            max_range=self.max_range)
        
        newTT.flights = [e.clone() for e in self.flights]
        
    """
    create a random timetable from available flights, starting with MTX,
    then permute
    """
    def randomise(self):        
        fltCln = (
                self.flight_manager.flights[self.base_airport.iata_code]
                [self.fleet_type.fleet_type_id]
                )
        mtx = (
                self.flight_manager.MTXFlights[self.base_airport.iata_code]
                [self.fleet_type.fleet_type_id]
                )
        self.flights = [mtx]
        self.recalc()
        
        # randomly choose available flights until nothing else can be added
        while True:
            newFlight = fltCln.getShorterFlight(self.remaining())
            if newFlight is None:
                break
            else:
                fltCln.delete(newFlight)
                self.appendFlight(newFlight)
                self.recalc()

        # permute order
        self.flights = list(list(itertools.permutations(self.flights))[
                rnd.randint(1, math.factorial(len(self.flights)))
                ])
        self.recalc()

       
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
        or f.flight.base_airport != self.base_airport 
        or (not f.flight.isMaintenance 
            and f.flight.fleet_type != self.fleet_type)):
            raise Exception("Invalid flight "
                            "passed to Timetable.append: {}".format(f))
            
        # check total length 
        if f.getLength() > self.remaining():
            return False
        
        # check whether this flight is already in the timetable
        for x in self.flights:
            if x == f or x.flight == f.flight:
                # don't raise an exception, just do nothing                
                # raise Exception("Flight [{}] already in timetable".
                # format(x.flight.flight_number))
                return False

        self.flights.append(f)

        self.next_start_day = f.available_day
        self.available_time = f.available_time
        
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
        return reduce(lambda a, x: a + x.getLength(), 
                      self.flights, timedelta(0,0))

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
        