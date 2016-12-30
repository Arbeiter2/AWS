from flights import Airport, Flight, FlightCollection, FlightCollectionIter, FleetType
from datetime import timedelta
from nptime import nptime
from nptools import str_to_timedelta, str_to_nptime, TimeIsInWindow, time_to_str
from collections import OrderedDict
import copy
import pdb
import json
import re

def nptime_diff_sec(a, b):
    if not isinstance(a, nptime) or not isinstance(b, nptime):
        return None
        
    diff = abs((a - b).seconds)
    if diff > 43200:
        return 86400 - diff
    else:
        return diff
        
        

class TimetableManager:
    """looks for conflicts"""
    def __init__(self):
        self.routes = {}
        self.ignore_base_timetables = False
        
    def setIgnoreBaseTimetables(self, status):
        if not isinstance(status, bool):
            raise Exception("Bad value passed to setIgnoreBaseTimetables")
            
        self.ignore_base_timetables = status
    
    def append(self, obj):
        """adds an entry with outbound and inbound departure times for each """
        """timetable entry it receives; can handle either TimetableEntry or """
        """Timetable objects as argumebt"""
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


    def filter(self, base_airport_iata, fleet_type_id):
        """create new TimetableManager instance, utilising flights with the
        specified base_airport_iata, but excluding a given fleet_type_id"""
        out = TimetableManager()
        
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
    
    def hasConflicts(self, ttEntry):
        '''
        this function replicates the PHP code of similar function
        '''
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
        if not isinstance(f, Flight):
            raise Exception("Invalid flight passed to TimetableEntry ctor")
        if not isinstance(tt, Timetable):
            raise Exception("Invalid timetable arg passed to TimetableEntry ctor")
            

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

        self.recalc()
        #self.adjust()

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
            
            
    def is_good(self):
        """checks whether the entry is worth keeping"""
        # reject flights exceeding maximum range of timetable
        if (self.parent.max_range 
        and self.flight.distance_nm > self.parent.max_range):
            return False

        # check available time first, as this applies to both flights and MTX;
        # if in operational curfew or base airport curfew,
        #   if parent timetable has MTX, 
        #       then fail as we will have nothing we can add sensibly;
        #   if parent timetable has no MTX, and this is MTX,
        #       then fail
        if (OpTimes.InDepCurfew(self.available_time) 
        or  self.flight.base_airport.in_curfew(self.available_time)):
            #pdb.set_trace()
            if (self.parent.hasMaintenance() 
            or (not self.parent.hasMaintenance 
            and self.flight.isMaintenance)):
                return False
            
        # all other times are irrelevant for MTX, so we leave here
        if self.flight.isMaintenance:
            return True
            
        # check airport curfews first
        if (self.flight.base_airport.in_curfew(self.outbound_dep) 
        or  self.flight.base_airport.in_curfew(self.inbound_arr) 
        or  self.flight.dest_airport.in_curfew(self.inbound_dep)
        or  self.flight.dest_airport.in_curfew(self.outbound_arr)):
            return False

        # check operation curfews next
        if (not self.parent.graveyard
        and (OpTimes.InDepCurfew(self.outbound_dep)
        or  OpTimes.InArrCurfew(self.outbound_arr) 
        or  OpTimes.InDepCurfew(self.inbound_dep)
        or  OpTimes.InArrCurfew(self.inbound_arr))):
            return False
            
        # check individual legs for curfew violations
        if self.flight.hasStops:
            res = self.checkLegCurfews()
            if res is not None:
                print(res)
                return False
            
        # look for conflicts with other flights on the same route
        if (self.parent.flight_manager 
        and self.parent.flight_manager.hasConflicts(self)):
            #print("Found collision for {}".format(str(self.flight)))
            return False
            
        return True

    def checkLegCurfews(self):
        # check whether any legs are in breach of curfew at the tech stop
        #print ("Checking curfews for {}".format(self.flight.__str__()))
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
                    return "{} closed at arrival time {}".format(
                        leg['end_airport'].iata_code, arr)
                
                if leg['end_airport'].in_curfew(dep):
                    return "{} closed at departure time {}".format(
                        leg['end_airport'].iata_code, dep)
                
                # ready for the next hop, where this becomes the start_airport
                start = dep

        return None        
        
    def adjust(self):
        # do nothing if we're healthy already
#        if (self.is_good()):
#            return
            
        # find the effective inbound curfew
        inbound_curfew_start = OpTimes.LatestDep
        inbound_curfew_finish = OpTimes.EarliestDep

        if self.flight.dest_airport.curfew_start is not None:
            if (self.flight.dest_airport.curfew_start - OpTimes.LatestDep >
                    timedelta(hours=12)):
                inbound_curfew_start = self.flight.dest_airport.curfew_start

            if self.flight.dest_airport.curfew_finish > OpTimes.EarliestDep:
                inbound_curfew_finish = self.flight.dest_airport.curfew_finish
                
        
        # if the end of the curfew is not too far away, add some padding to
        # the destination turnaround
#        if TimeIsInWindow(self.inbound_dep, inbound_curfew_start, 
#            inbound_curfew_finish):
#            stt = self.inbound_dep.strftime("%H:%M")
#            delta = timedelta(seconds=(
#                inbound_curfew_finish - 
#                self.inbound_dep + 
#                timedelta(seconds=600)).seconds)
#            if delta < self.max_padding:
#                #pass
#                self.dest_turnaround_padding += delta
                #print("Padding inbd {} from {} to {} ({})".format(
                 #   str(self.flight), stt, 
                  #  self.inbound_dep + delta,
                  #  self.dest_turnaround_padding))

        # find the effective curfew for the next flight after this one
        outbound_curfew_start = OpTimes.LatestDep
        outbound_curfew_finish = OpTimes.EarliestDep
        
        # if the end of the curfew is not too far away, add some padding to
        # the base turnaround
        if TimeIsInWindow(self.available_time, outbound_curfew_start, 
            outbound_curfew_finish):
            stt = self.base_turnaround_length
            delta = timedelta(seconds=(
                outbound_curfew_finish - 
                self.available_time + 
                timedelta(seconds=600)).seconds)
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
        self.base_turnaround_length = self.fleet_type.ops_turnaround_length
        self.base_turnaround_delta = timedelta(seconds=0)
        self.graveyard = graveyard

        # by convention
        self.next_start_day = 1
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
            self.base_turnaround_length = delta + self.fleet_type.min_turnaround
            self.base_turnaround_delta = delta
        
        #print(self.base_turnaround_delta)        
        # optional
        self.flight_manager = None
        if fManager and isinstance(fManager, TimetableManager):
            self.flight_manager = fManager
            
        self.max_range = None
        if max_range is not None and max_range > 0:
            self.max_range = max_range
        
    
    def append(self, f):
        """add TimetableEntry"""
        # throw exception for invalid  arg
        if (not isinstance(f, TimetableEntry) 
        or f.flight.base_airport != self.base_airport 
        or (not f.flight.isMaintenance 
            and f.flight.fleet_type != self.fleet_type)):
            print(self.timetable_id, f.flight.base_airport, 
                self.base_airport, f.flight.fleet_type, self.fleet_type)
            raise Exception("Invalid flight passed to Timetable.__add__: {}".format(f))
            
        # check whether this flight is already in the timetable
        for x in self.flights:
            if x == f or x.flight == f.flight:
                raise Exception("Flight [{}] already in timetable".
                format(x.flight.flight_number))

        self.flights.append(f)

        self.next_start_day = f.available_day
        self.available_time = f.available_time
                
    def __add__(self, f):
        out = copy.copy(self)
        out.flights = copy.copy(self.flights)
        out.append(f)

        return out
        
    def __str__(self):
        out = "[\n"
        for e in self.flights:
            out += str(e)
        return out + "]\nNext start day: {}; Next available: {}; Total time: {}".format(self.next_start_day, self.available_time, self.total_time())

    def lex(self):
        """return a comma-separated list of flights in this timetable"""
        return ",".join(sorted(map(lambda x: x.flight.flight_number, self.flights)))

    def seq(self):
        """return a comma-separated list of flights in this timetable"""
        return ",".join(map(lambda x: x.flight.flight_number, self.flights))       
    
    def to_dict(self):
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
        
    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)

    def isEmpty(self):
        return len(self.flights) == 0
        
    def total_time(self):
        """find aggregate utilisation (ish)"""
        total = timedelta(0,0)
        
        for entry in self.flights:
            total += entry.total_time
            
        return total

    def hasMaintenance(self):
        for entry in self.flights:
            if entry.flight.isMaintenance:
                return True
                
        return False
        
        
    def is_good(self, threshold):
        """check how close total is to 168 hours, and whether we have MTX"""
        #print("ratio = {:.2}%".format(self.total_time().total_seconds()/(7 * 86400) * 100.0))
        if (self.total_time().total_seconds()/(7 * 86400) < threshold):
            return False
            
        if (self.total_time().total_seconds() > (7 * 86400)):
            return False
        
        return self.hasMaintenance()
