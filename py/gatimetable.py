# -*- coding: utf-8 -*-

from nptools import str_to_timedelta, str_to_nptime
from datetime import timedelta
from timetables import Timetable, TimetableEntry, TimetableManager
import random as rnd
from flights import FlightManager, FlightCollection


"""
A genetic algorithm engine for creating a timetable.

Each flight is represented by its index position in the flight collection list
of flights.
@author: Delano
"""
class GATimetable:
    def __init__(self, ttManager=None, flManager=None):
        if (not isinstance(ttManager, TimetableManager)
        or  not isinstance(flManager, FlightManager)):
            print("#P{} {}".format(str(ttManager), str(FlightManager)))
            raise Exception("GATimetable(): Invalid args")
            
        if not isinstance(flManager, FlightManager):
            raise Exception("No valid FlightManager provided")
        self.flManager = flManager

        if not isinstance(ttManager, TimetableManager):
            raise Exception("No valid TimetableManager provided")
        self.ttManager = ttManager
        
        if self.flManager.source != self.ttManager.source:
            raise Exception(
                "Differing sources between FlightManager/TimetableManager"
            )
 
        
    """
    create initial population of random timetables and flight collections
    """
    def initPopulation(self, popSize, base_airport, fleet_type, 
                       outbound_dep=None, base_turnaround_delta=None, 
                       max_range=None, add_mtx_gap=True, graveyard=True, 
                       ignore_existing=False):
        if popSize <= 0:
            return None
        
        # all flight collections will be the same
        self.origFltCln = self.ttManager.getFlightCollection(
                            base_airport_iata=base_airport.iata_code, 
                            fleet_type_id=fleet_type.fleet_type_id,
                            max_range=max_range,
                            ignore_existing=ignore_existing
                     )
        print("origFltCln:\n{}".format(self.origFltCln.status()))
        fltClns = [self.origFltCln.clone() for _ in range(0, popSize)]

        # popSize random timetables
        popn = [Timetable(
                   self.ttManager, 
                   base_airport=base_airport, 
                   fleet_type=fleet_type, 
                   outbound_dep=outbound_dep, 
                   base_turnaround_delta=base_turnaround_delta, 
                   max_range=max_range, 
                   graveyard=graveyard).randomise(fltClns[i])
              for i in range(0, popSize)]
        
#        for x in range(len(popn)):
#            if popn[x].total_time() < timedelta(days=6):
#                print("bad news at [{}]\n{}".format(x, popn[x]))
#            

        return popn, fltClns
    

    """
    write best-scoring timetable in population, and replace entire population 
    with new randomly generated entries, which will not use flights from 
    promoted winner
    """
    def promote(self, population, fltClns, bestIndex, populateFn):
        if not isinstance(population, list):
            return population, fltClns
        
        if bestIndex not in range(0, len(population)):
            return population, fltClns
        
        # verify bestIndex-th entry is indeed good
        if population[bestIndex].getScore() != 0.0:
            return population, fltClns
        
        print("Winner:\n{}".format(population[bestIndex]))
        
        self.ttManager.append(population[bestIndex])
        
        return populateFn()
    
    """
    get scores for a given population
    """
    def getScores(self, popn):
        popSize = len(popn)
        scores = [tt.getScore() for tt in popn]
                  
        # list indexes in sorted order
        scoreIndexes = [b[0] for b in sorted(enumerate(scores),
                        key=lambda i:i[1])]
        
        maxScore = scores[scoreIndexes[popSize-1]]
        minScore = scores[scoreIndexes[0]]
        meanScore = sum(scores)/popSize
        
        return scores, scoreIndexes, maxScore, minScore, meanScore
    
    
    """
    create offspring from randomly chosen subset of existing population
    """
    def getOffspring(self, popn, fltClns, childCount):
        newPopn = []
        newFltClns = []
        
        indexes = list(range(len(popn)))
        rnd.shuffle(indexes)
        
        # create children, all hopefully better than the parents
        for i in range(0, childCount):
            parent = popn[indexes[i]]
            parentfltCln = fltClns[indexes[i]]
            
            child, childFltCln, status = self.biasMutate(parent, parentfltCln)

            newPopn.append(child)
            newFltClns.append(childFltCln)
            
        return newPopn, newFltClns
    
    
    def findDuplicates(self, popn):
        keys = [",".join(x.seq()) for x in popn]
        keyFreq = [keys.count(p) for p in keys]
        
        for i in range(len(keys)):
            if keyFreq[i] > 1:
                print("Duplicate entries for \n{}".format(popn[i]))
    
    
        
    """
    run simulation for new population of timetables
    
    Params:
    popSize = population size
    maxGenerations = max. generation count
    mutProb = mutation probability
    eliteProp = elite proportion to retain
    """
    def run(self, base_airport_iata, fleet_type_id, outbound_dep=None, 
            base_turnaround_delta=None, max_range=None, 
            add_mtx_gap=True, graveyard=True, ignore_existing=False,
            popSize=100, maxGenerations=40, mutProb=0.05,
            eliteProp=0.01):
        if (base_airport_iata not in self.flManager.flights
            or fleet_type_id not in self.flManager.flights[base_airport_iata]):
            raise Exception("__call__ args: base_airport_iata = {}; "
                            "fleet_type_id = {}".format(base_airport_iata,
                                                        fleet_type_id))

        base_airport = self.flManager.airports[base_airport_iata]
        fleet_type = self.flManager.fleet_types[fleet_type_id]
        self.ttManager.setMTXGapStatus(base_airport_iata, fleet_type_id, 
                                       add_mtx_gap)

        # if no turnaround delta is supplied, use default for fleet type
        delta = str_to_timedelta(base_turnaround_delta)
        if (delta is not None 
        and delta + fleet_type.min_turnaround >= 
                fleet_type.ops_turnaround_length):
            base_turnaround_delta = delta
        else:
            base_turnaround_delta = (
                    fleet_type.ops_turnaround_length - 
                    fleet_type.min_turnaround
                    )

        if not str_to_nptime(outbound_dep):
            outbound_dep = base_airport.getRandomStartTime()

        def populate():
             return self.initPopulation(popSize, base_airport, 
                                   fleet_type, outbound_dep, 
                                   base_turnaround_delta, 
                                   max_range, add_mtx_gap, graveyard, 
                                   ignore_existing)
             
        popn, fltClns = populate()
        
        
        # elite count
        eliteCnt = int(popSize * eliteProp)
        childCount = int(popSize * mutProb)
        
        # run until various conditions hit
        gen = 0
        while True:
#            for x in range(popSize):
#                if popn[x].total_time() < timedelta(days=6):
#                    print("bad news at [{}]\n{}\n{}".format(x, popn[x], fltClns[x].status()))
 
            #self.findDuplicates(popn)
            gen = gen + 1

            if gen > maxGenerations:
                break
            
            (scores, scoreIndexes,
             maxScore, minScore, meanScore) = self.getScores(popn)

            print("{}:\t{}\t{}\t{}".format(gen, minScore, 
                  meanScore, maxScore))

            # if winner found, build new population and start new sim
            if scores[scoreIndexes[0]] == 0:
                gen = 0
                
                # write out winning timetable, and start new iterations
                popn, fltClns = self.promote(popn, fltClns, 
                                             scoreIndexes[0],
                                             populate)
                continue

            newPopn = []
            newFltClns = []
            
            # get elites
            newPopn.extend([popn[i] for i in scoreIndexes[0:eliteCnt]])
            newFltClns.extend([fltClns[i] for i in scoreIndexes[0:eliteCnt]])
            
            # create offspring from total population
            x, y = self.getOffspring(popn, fltClns, childCount)
            newPopn.extend(x)
            newFltClns.extend(y)

            for i in range(len(newPopn), popSize):
                newFltClns.append(self.origFltCln.clone())
                newPopn.append(Timetable(
                           self.ttManager, 
                           base_airport=base_airport, 
                           fleet_type=fleet_type, 
                           outbound_dep=outbound_dep, 
                           base_turnaround_delta=base_turnaround_delta, 
                           max_range=max_range, 
                           graveyard=graveyard).randomise(newFltClns[i]))
                self.tweak(newPopn[i], newFltClns[i])
                
            # replace population
            popn = newPopn
            fltClns = newFltClns
            self.removeDuplicates(popn, fltClns)
            
        scores = [tt.getScore() for tt in popn]
        for i in range(0, eliteCnt):
            print(popn[i])


    """
    return index of highest scoring (i.e. worst performing) allele/flight
    in chromosome
    """            
    def highestScoringIndex(self, tt):
        entryScores = tt.getMetaData()
        
        return max(range(len(entryScores)), key=entryScores.__getitem__)
    
    """
    adjust worst scoring entry
    """
    def adjust(self, tt, score=None):
        if not isinstance(tt, Timetable):
            raise Exception("Invalid Timetable [{}]".format(tt))

        worst = list(filter(lambda x: tt.flights[x].metaScore.get() != 0.0, 
                            range(0, len(tt.flights))))
        
        if len(worst) == 0:
            return True

        for wIndex in worst:
            oldFlight = tt.flights[wIndex].clone()
            tt.flights[wIndex].adjust()
            tt.recalc()
            
            if tt.getScore() >= score:
                tt.flights[wIndex] = oldFlight
    
        return tt.getScore() < score
       
    """
    swap worst scoring flight for others in timetable, until score is improved 
    or all flights have been tried
    """
    def swapInPlace(self, tt, score=None):
        if not isinstance(tt, Timetable):
            raise Exception("Invalid Timetable")
        
        if score == 0.0:
            return True

        worst = list(filter(lambda x: tt.flights[x].metaScore.get() != 0.0, 
                            range(0, len(tt.flights))))
        
        oldFlights = tt.flights[:]

        # find element with highest score and swap with everything else 
        # until we get a lower score
        for wIndex in worst:
            for idx in range(0, len(tt.flights)):
                if idx == wIndex:
                    continue
                temp = tt.flights[wIndex]
                tt.flights[wIndex] = tt.flights[idx]
                tt.flights[idx] = temp
                tt.recalc()
                
                if tt.getScore() >= score:
                    tt.flights = oldFlights[:]
                else:
                    oldFlights = tt.flights[:]
            
        return tt.getScore() < score

    """
    swap out worst scoring flight for another, until score is improved or no
    more flights available
    """
    def swapOut(self, tt, fltCln, score=None):
        if not isinstance(tt, Timetable):
            raise Exception("Invalid Timetable")
        if not isinstance(fltCln, FlightCollection):
            raise Exception("Invalid FlightCollection")
        
        if score == 0.0:
            return True

        worst = list(filter(lambda x: tt.flights[x].metaScore.get() != 0.0, 
                            range(0, len(tt.flights))))

        # find element with highest score and swap with something else 
        # from fltCln until we get a lower score
        for wIndex in worst:
            oldEntry = tt.flights[wIndex]
            oldFlight = tt.flights[wIndex].flight
            ofLength = oldFlight.length() + tt.remaining()

            for newFlight in fltCln.ordered():
                if tt.contains(newFlight):
                    pass
                if newFlight.length() > ofLength:
                    newFlight = None
                    break
                #print("{} {}".format(newFlight.flight_number, newFlight.length()))
                newEntry = TimetableEntry(newFlight, tt)
                tt.flights[wIndex] = newEntry
                tt.recalc()
                
                if score is None or tt.getScore() < score:
                    fltCln.undelete(oldFlight)
                    fltCln.delete(newFlight)
                    return True
                else:
                    newFlight = None
        
            tt.flights[wIndex] = oldEntry
            tt.recalc()

            
        return False
    
    """
    reverse order of subsequence of flight events
    """
    def invert(self, tt, score=None, invertCount=3):
        if not isinstance(tt, Timetable):
            raise Exception("Invalid Timetable")
            
        if score == 0.0:
            return True

        oldFlights = tt.flights[:]

        for run in range(0, invertCount):
            # random selection of two points within flight list
            [startIndex, endIndex] = sorted(rnd.sample(range(len(tt.flights)),
                                                                 k=2))
            
            # reverse list segment between start and end
            rev = list(reversed(tt.flights[startIndex:endIndex]))[:]
            
            # copy reversed segment back
            tt.flights[startIndex:endIndex] = rev
            tt.recalc()
            if score is None or tt.getScore() < score:
                return True
            else:
                tt.flights = oldFlights
                tt.recalc()

        return False
    
    """
    try changing start time 
    """
    def startTimes(self, tt, score=None, tryCount=20):
        if not isinstance(tt, Timetable):
            raise Exception("Invalid Timetable")
        
        origStartTime = tt.start_time
        
        for _ in range(tryCount):
            tt.start_time = tt.base_airport.getRandomStartTime()
            tt.recalc()
            
            if score is None or tt.getScore() < score:
                return True
            
        tt.start_time = origStartTime
        tt.recalc()
        
        return False
    
    """
    permute order of flights in timetable, up to permuteCount times, stop
    if score is improved
    """
    def permute(self, tt, score=None, permuteCount=30):
        if not isinstance(tt, Timetable):
            raise Exception("Invalid Timetable")

        #oldFlights = tt.flights[:]

        # use all but the first (zeroth) entry
        for run in range(0, permuteCount):
            #rnd.shuffle(tt.flights)
            tt.flights = rnd.sample(tt.flights, k=len(tt.flights))
            tt.recalc()

            if score is None or tt.getScore() < score:
                return True
        
        #tt.flights = oldFlights
        tt.recalc()
        return False
    
    """
    tweak a timetable, hopefully reducing score
    """
    def tweak(self, tt, fltCln):
        if not isinstance(tt, Timetable):
            raise Exception("tweak(): Invalid args [{}]".format(tt))
            
        if not isinstance(fltCln, FlightCollection):
            raise Exception("Invalid FlightCollection")
            
        score = tt.getScore()
            
        # try changing stsrt time
        #if self.startTimes(tt, score):
        #    pass
            #print("biasMutate: startTimes")
            #return tt, fltCln, True
 
        #
        if self.adjust(tt, score):             
            pass
            #print("biasMutate: adjust")
            #return tt, fltCln, True
 
         #
        if self.swapInPlace(tt, score):
            pass
            #print("biasMutate: swapInPlace {} -> {}".format(score, tt.getScore()))
            #return tt, fltCln, True
         
        if self.swapOut(tt, fltCln, score):
            pass
            #print("biasMutate: swapOut")
            #return tt, fltCln, True
         
        # aggressive penultimate resort
        if self.invert(tt, score):
            pass
            #print("biasMutate: invert")
            #return tt, fltCln, True
            
        return tt.getScore() < score

    
    """
    spawn lower-score mutated child of timetable, trying methods with following
    order of precedence:
        
        adjust - modify turnaround padding of worst scoring flight 
        swapInPlace - swap worst scoring flight with others in-situ
        swapOut - swap worst scoring flight with one from pool
        permute - permute order of flights
        
    always returns child
        
    returns True if the Timetable has a reduced score
    returns False otherwise
    """
    def biasMutate(self, parent, parentFltCln):
        if not isinstance(parent, Timetable):
            raise Exception("mutate(): Invalid args [{}]".format(parent))
            
        if not isinstance(parentFltCln, FlightCollection):
            raise Exception("Invalid FlightCollection")
            
        score = parent.getScore()
        
        #print("biasMutate {}".format(score))
        
        tt = parent.clone()
        fltCln = parentFltCln.clone()
        
        # aggressive
        self.permute(tt, score)
        
        self.tweak(tt, fltCln)
       
        if tt.getScore() >= score:
            fltCln.reset()
            tt.randomise(fltCln)
            
        #print("biasMutate: randomise {}/{}".format(score, tt.getScore()))
        
        #print ("scores: {}, {}".format(score, tt.getScore()))
        return tt, fltCln, True
    
    """
    finds duplicates and replaces them with randomised entries
    """
    def removeDuplicates(self, popn, fltClns):
        hashMap = dict()
        
        # hash each entry and build list of dupicates
        for index in range(0, len(popn)):
            key = popn[index].hash()
            if key not in hashMap:
                hashMap[key] = []
            hashMap[key].append(index)
            
        for key in hashMap:
            if len(hashMap[key]) > 1:
                print("removeDuplicates: {} x {}".format(key, len(hashMap[key])))
                # save the first one, replace the rest
                for i in range(1, len(hashMap[key])):
                    cln = fltClns[hashMap[key][i]]
                    cln.reset()
                    popn[hashMap[key][i]].randomise(cln)

        
    
    """
    spawn mutated child of timetable, trying methods with following
    order of precedence:
        
        swapInPlace - swap flight with another in-situ
        swapOut - swap worst scoring flight with one from pool
        permute - permute order of flights
        
    returns child
    """
    def randMutate(self, parent, parentFltCln):
        if not isinstance(parent, Timetable):
            raise Exception("randMutate(): Invalid args [{}]".format(parent))
            
        if not isinstance(parentFltCln, FlightCollection):
            raise Exception("Invalid FlightCollection")
            
        tt = parent.clone()
        fltCln = parentFltCln.clone()

        index = rnd.randrange(5)
        
        if index == 0:
            self.swapInPlace(tt)
        elif index == 1:
            self.invert(tt)
        elif index == 2:
            self.swapOut(tt, fltCln)
        elif index == 3:
            self.invert(tt)
        elif index == 4:
            self.permute(tt)
            
        return tt, fltCln, True
        
