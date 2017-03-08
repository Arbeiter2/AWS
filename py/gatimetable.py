# -*- coding: utf-8 -*-
"""
A genetic algorithm version of a timetable.

Each flight is represented by its index position in the flight collection list
of flights.
@author: Delano
"""
from nptime import nptime
from nptools import str_to_timedelta
import math
from timetables import Timetable, TimetableManager
import random as rnd
from itertools import permutations
from flights import Airport, FleetType, FlightCollection


class TimetableMutator:
    
    def init(self, mut_prob, fltCln):
        if not isinstance(fltCln, FlightCollection):
            raise Exception("Invalid FlightCollection")
            
        self.mutation_prob = mut_prob
        self.fltCln = fltCln
        
    def highestScoringIndex(self, tt):
        entryScores = tt.getMetaData()
        
        return max(range(len(entryScores)), key=entryScores.__getitem__)
    
    """
    adjust worst scoring entry
    """
    def __adjust(self, tt, score):
        highestScoringIndex = self.highestScoringIndex(tt)

        tt.flights[highestScoringIndex].adjust()
        tt.recalc()
        return tt.getScore() < score

        
    """
    swap worst scoring flight for others in timetable, until score is improved 
    or all flights have been tried
    """
    def __swapInPlace(self, tt, score):
        highestScoringIndex = self.highestScoringIndex(tt)

        # find element with highest score and swap with everything else 
        # until we get a lower score
        for testIndex in range(0, len(tt.flights)):
            if testIndex == highestScoringIndex:
                continue
            temp = tt.flights[testIndex]
            tt.flights[highestScoringIndex] = tt.flights[testIndex]
            tt.flights[testIndex] = temp
            tt.recalc()
            
            if tt.getScore() < score:
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
    def __swapOut(self, tt, score):
        highestScoringIndex = self.highestScoringIndex(tt)

        oldFlight = tt.flights[highestScoringIndex].flight
        ofLength = oldFlight.length() + tt.remaining()

        # find element with highest score and swap with something else 
        # from fltCln until we get a lower score
        while True:
            newFlight = self.fltCln.getShorterFlight(ofLength, random=False)
            if newFlight is None:
                break
            tt.flights[highestScoringIndex].flight = newFlight
            tt.recalc()
            
            if tt.getScore() < score:
                break
            else:
                newFlight = None
        
        if newFlight is None:
            tt.flights[highestScoringIndex].flight = oldFlight
            return False
        else:
            return True
    
    """
    permute order of flights in timetable, up to permuteCount times, stop
    if score is improved
    """
    def __permute(self, tt, score, permuteCount=3):
        oldFlights = tt.flights

        # use all but the first (zeroth) entry
        for run in range(0, permuteCount):
            rndIndex = rnd.randint(1, math.factorial(len(tt.flights))-1)
            flights = list(list(permutations(tt.flights))[rndIndex])
            tt.flights = flights
            tt.recalc()

            if tt.getScore() < score:
                return True
        
        tt.flights = oldFlights
        tt.recalc()
        return False
    
    """
    try mutating a timetable, until the score is reduced, with following
    order of precedence:
        
        adjust - modify turnaround padding of worst scoring flight 
        swapInPlace - swap worst scoring flight with others in-situ
        swapOut - swap worst scoring flight with one from pool
        permute - permute order of flights
        
    returns True if the Timetable has a reduced score
    returns False otherwise
    """
    def mutate(self, tt):
        if not isinstance(tt, Timetable):
            raise Exception("mutate(): Invalid args [{}]".format(tt))
            
        score = tt.getScore()
        if score == 0:
            return True
            
        p = rnd.random()
        if p >= self.mutation_prob:
            return False
        
        if self.__adjust(tt, score):
            return True
        
        if self.__swapInPlace(tt, score):
            return True
        
        if self.__swapOut(tt, score):
            return True
        
        if self.__permute(tt, score):
            return True
        
        # no mutation attempts resulted in improved score 
        return False
      
        
    
class GATimetable:
    def __init__(self, ttManager, 
                 base_airport, fleet_type, 
                 outbound_dep, 
                 base_turnaround_delta=None, 
                 max_range=None, 
                 graveyard=True,
                 ignore_base_timetables=False):
        if (not isinstance(ttManager, TimetableManager)
        or  not isinstance(base_airport, Airport) 
        or  not isinstance(fleet_type, FleetType)
        or  not isinstance(outbound_dep, nptime)):
            print("##P{} {} {} {}".format(str(ttManager), str(base_airport), 
                  str(fleet_type), outbound_dep))
            raise Exception("GATimetable(): Invalid args")
            
        self.ttManager = ttManager
        self.base_airport = base_airport
        self.fleet_type = fleet_type

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
        self.graveyard = graveyard
        self.max_range = max_range
        self.outbound_dep = outbound_dep
        self.ignore_base_timetables = ignore_base_timetables
        
        # GA components
        self.population = []
        self.bestScores = []
        self.generation = 0
        
    """
    create initial population of random timetables and flight collections
    """
    def initPopulation(self, popSize):
        if popSize <= 0:
            return None
        
        # popSize random timetables
        popn = [Timetable(
                   self.ttManager, 
                   base_airport=self.base_airport, 
                   fleet_type=self.fleet_type, 
                   outbound_dep=self.outbound_dep, 
                   base_turnaround_delta=self.base_turnaround_delta, 
                   max_range=self.max_range, 
                   graveyard=self.graveyard).randomise()
              for _ in range(0, popSize)]
    
        # all flight collections will be the same
        origFltCln = self.ttManager.getFlightCollection(
                            base_airport_iata=self.base_airport.iata_code, 
                            fleet_type_id=self.fleet_type.fleet_type_id,
                            max_range=self.max_range,
                            ignore_base_timetables=self.ignore_base_timetables
                     )
        fltClns = [origFltCln.clone() for _ in range(0, popSize)]

        return popn, fltClns
    

    """
    write best-scoring timetable in population, and replace entire population 
    with new randomly generated entries, which will not use flights from 
    promoted winner
    """
    def promote(self, population, fltClns, bestIndex):
        if not isinstance(population, list):
            return population, fltClns
        
        if bestIndex not in range(0, len(population)):
            return population, fltClns
        
        # verify bestIndex-th entry is indeed good
        if population[bestIndex].getScore() != 0.0:
            return population, fltClns
        
        self.ttManager.append(population[bestIndex])
        
        return self.initPopulation(len(population))
