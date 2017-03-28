# -*- coding: utf-8 -*-

from nptools import str_to_timedelta, str_to_nptime
import math
from timetables import Timetable, TimetableManager
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
            print("##P{} {}".format(str(ttManager), str(FlightManager)))
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
        origFltCln = self.ttManager.getFlightCollection(
                            base_airport_iata=base_airport.iata_code, 
                            fleet_type_id=fleet_type.fleet_type_id,
                            max_range=max_range,
                            ignore_existing=ignore_existing
                     )
        fltClns = [origFltCln.clone() for _ in range(0, popSize)]

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
            popSize=50, maxGenerations=100, mutProb=0.25,
            eliteProp=0.1):
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
        
        # proportion to use as parents
        parentCnt = int(popSize * mutProb)
        
        # children per parent
        # if there was rounding, low-scoring parents get one more child
        childCnt = (popSize - eliteCnt) // parentCnt
        
        # run until various conditions hit
        gen = 0
        while True:
            gen = gen + 1

            if gen > maxGenerations:
                break
            
            # get scores
            scores = [tt.getScore() for tt in popn]
                      
            # list indexes in sorted order
            scoreIndexes = [b[0] for b in sorted(enumerate(scores),
                            key=lambda i:i[1])]
            
            maxScore = scores[scoreIndexes[popSize-1]]
            minScore = scores[scoreIndexes[0]]
            meanScore = sum(scores)/popSize

            print("{}:\t{}\t{}\t{}".format(gen, minScore, meanScore, maxScore))

            # if winner found, build new population and start new sim
            if scores[scoreIndexes[0]] == 0:
                gen = 0
                
                # write out winning timetable, and start new iterations
                popn, fltClns = self.promote(popn, fltClns, 
                                             scoreIndexes[0],
                                             populate)
                continue

            newPopn = []
            
            # get elites
            newPopn.extend([popn[i] for i in scoreIndexes[0:eliteCnt]])
            
            # create remaining children
            for i in range(0, parentCnt):
                parent = popn[scoreIndexes[i]]
                fltCln = fltClns[scoreIndexes[i]]

                # highest scorers get an extra child each to complete set
                if popSize != len(newPopn) + childCnt * (parentCnt - i):
                    localCnt = childCnt + 1
                else:
                    localCnt = childCnt

                newPopn.extend([self.biasMutate(parent, fltCln)[0] 
                                for _ in range(localCnt)])
            
            # replace population
            popn = newPopn


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
    def adjust(self, tt, score):
        if not isinstance(tt, Timetable):
            raise Exception("Invalid Timetable [{}]".format(tt))

        highestScoringIndex = self.highestScoringIndex(tt)

        tt.flights[highestScoringIndex].adjust()
        tt.recalc()
        return tt.getScore() < score

        
    """
    swap worst scoring flight for others in timetable, until score is improved 
    or all flights have been tried
    """
    def swapInPlace(self, tt, score=None):
        if not isinstance(tt, Timetable):
            raise Exception("Invalid Timetable")

        if score is not None:
            highestScoringIndex = self.highestScoringIndex(tt)
        else:
            highestScoringIndex = rnd.choice(range(0, len(tt.flights)))

        # find element with highest score and swap with everything else 
        # until we get a lower score
        for testIndex in range(0, len(tt.flights)):
            if testIndex == highestScoringIndex:
                continue
            temp = tt.flights[testIndex]
            tt.flights[highestScoringIndex] = tt.flights[testIndex]
            tt.flights[testIndex] = temp
            tt.recalc()
            
            if score is None or tt.getScore() < score:
                break
            else: # swap them back
                temp = tt.flights[highestScoringIndex]
                tt.flights[testIndex] = tt.flights[highestScoringIndex]
                tt.flights[highestScoringIndex] = temp
            
        return False

    """
    swap out worst scoring flight for another, until score is improved or no
    more flights available
    """
    def swapOut(self, tt, fltCln, score=None):
        if not isinstance(tt, Timetable):
            raise Exception("Invalid Timetable")
        if not isinstance(fltCln, FlightCollection):
            raise Exception("Invalid FlightCollection")
        
        if score is not None:
            highestScoringIndex = self.highestScoringIndex(tt)
        else:
            highestScoringIndex = rnd.choice(range(0, len(tt.flights)))

        oldFlight = tt.flights[highestScoringIndex].flight
        ofLength = oldFlight.length() + tt.remaining()

        # find element with highest score and swap with something else 
        # from fltCln until we get a lower score
        for newFlight in fltCln.ordered():
            if newFlight.length() > ofLength:
                newFlight = None
                continue
            #print("{} {}".format(newFlight.flight_number, newFlight.length()))
            tt.flights[highestScoringIndex].flight = newFlight
            tt.recalc()
            
            if score is None or tt.getScore() < score:
                break
            else:
                newFlight = None
        
        if newFlight is None:
            tt.flights[highestScoringIndex].flight = oldFlight
            return False
        else:
            fltCln.delete(newFlight)
            return True
    
    """
    reverse order of subsequence of flight events
    """
    def invert(self, tt, score=None, invertCount=3):
        if not isinstance(tt, Timetable):
            raise Exception("Invalid Timetable")
            
        oldFlights = tt.flights[:]

        for run in range(0, invertCount):
            # random selection of two points within flight list
            [startIndex, endIndex] = sorted(rnd.sample(range(len(tt.flights)),
                                                                 k=2))
            
            # reverse list segment between start and end
            rev = reversed(tt.flights[startIndex:endIndex])
            
            # copy reversed segment back
            tt.flights[startIndex:endIndex+1] = rev
            tt.recalc()
            if score is None or tt.getScore() < score:
                return True
        
        tt.flights = oldFlights
        tt.recalc()
        return False
    
    
    """
    permute order of flights in timetable, up to permuteCount times, stop
    if score is improved
    """
    def permute(self, tt, score=None, permuteCount=3):
        if not isinstance(tt, Timetable):
            raise Exception("Invalid Timetable")

        oldFlights = tt.flights[:]

        # use all but the first (zeroth) entry
        for run in range(0, permuteCount):
            rnd.shuffle(tt.flights)
            tt.recalc()

            if score is None or tt.getScore() < score:
                return True
        
        tt.flights = oldFlights
        tt.recalc()
        return False
    
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
    def biasMutate(self, parent, fltCln):
        if not isinstance(parent, Timetable):
            raise Exception("mutate(): Invalid args [{}]".format(parent))
            
        if not isinstance(fltCln, FlightCollection):
            raise Exception("Invalid FlightCollection")
            
        score = parent.getScore()
        
        #print("biasMutate {}\n{}".format(score, parent))
        
        tt = parent.clone()

        # aggressive first resort
        if self.permute(tt, score):
            return tt, True

        if self.adjust(tt, score):
            return tt, True
        
        if self.swapInPlace(tt, score):
            return tt, True

        if self.swapOut(tt, fltCln, score):
            return tt, True
        
        # aggressive penultimate resort
        if self.invert(tt, score):
            return tt, True

        
        return tt, False
    
    """
    spawn mutated child of timetable, trying methods with following
    order of precedence:
        
        swapInPlace - swap flight with another in-situ
        swapOut - swap worst scoring flight with one from pool
        permute - permute order of flights
        
    returns child
    """
    def randMutate(self, parent, fltCln):
        if not isinstance(parent, Timetable):
            raise Exception("randMutate(): Invalid args [{}]".format(parent))
            
        if not isinstance(fltCln, FlightCollection):
            raise Exception("Invalid FlightCollection")
            
        tt = parent.clone()
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
            
        return tt, True
        
