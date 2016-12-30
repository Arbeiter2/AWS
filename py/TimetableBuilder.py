#!/usr/bin/python3

from flights import Airport, Flight, FleetType, FlightCollection, \
    MaintenanceCheckA
from timetables import Timetable, TimetableEntry, TimetableManager, OpTimes
from mysql import connector
from mysql.connector.errors import Error
import pymysql
import requests
import random
import simplejson as json
from threading import Timer
from datetime import timedelta
from nptools import str_to_timedelta, str_to_nptime, timedelta_to_hhmm
from nptime import nptime
import pdb


class ThreadController:
    threadStop = False
    timerObj = None
    timerLimit = 0.0

    @staticmethod
    def start(x):
        if not (float(x) > 0.0):
            return False

        ThreadController.timerLimit = x

        if ThreadController.timerObj:
            ThreadController.stop()

        ThreadController.timerObj = Timer(ThreadController.timerLimit,
                                          ThreadController.stop)
        ThreadController.threadStop = False
        # print("Start")

        ThreadController.timerObj.start()

        return True

    @staticmethod
    def stop():
        if not ThreadController.timerObj:
            return False

        ThreadController.timerObj.cancel()
        ThreadController.threadStop = True
        ThreadController.timerObj = None
        # print("Timeout")

        return True

    @staticmethod
    def running():
        return not ThreadController.threadStop

    @staticmethod
    def reset():
        if (ThreadController.threadStop
            and ThreadController.timerObj is not None):
            ThreadController.threadStop = False
            ThreadController.timerObj = Timer(ThreadController.timerLimit,
                                              ThreadController.stop)
            ThreadController.timerObj.start()


class TimetableBuilder:
    def __init__(self, game_id, use_rejected=False, shuffle=True,
                 db_user='mysql',
                 db_pass='password', db_host='localhost', db_name='airwaysim',
                 db_port=3306):
        # all timetables at all bases
        # stored as timetables[base_airport_iata][fleet_type_id]
        self.timetables = {}

        # all flights at all bases
        # stored as flights[base_airport_iata][fleet_type_id]
        self.flights = {}
        self.airports = {}
        self.fleet_types = {}
        self.ttManager = TimetableManager()
        self.rejected = []
        self.use_rejected = use_rejected
        self.MTXFlights = {}
        self.shuffle_flights = shuffle
        self.game_id = game_id

        self.db_user = db_user
        self.db_pass = db_pass
        self.db_host = db_host
        self.db_name = db_name
        self.db_name = db_name
        self.db_port = db_port

        if not self.getFlights():
            raise Exception("Unable to load flights")
        else:
            print("Loaded {} flights".format(len(self.flight_lookup.keys())))

        if not self.getTimetables():
            raise Exception("Unable to load timetables")
        else:
            print("Loaded timetables from {} bases".format(
                len(self.timetables.keys())))

    def refresh(self):
        pass

    def getFlights(self):
        #cnx = pymysql.connect(user=self.db_user, password=self.db_pass,
        #                      host=self.db_host, db=self.db_name)
        #cursor = cnx.cursor(pymysql.cursors.DictCursor)

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

        # base airports
        uri = "http://localhost/aws/app/v1/games/" + self.game_id + "/bases"

        r = requests.get(uri)
        if r.status_code != 200:
            return False

        data = json.loads(r.text)['airports']
        # print("bases:\n{}".format(data))

        for row in data[0]['bases']:
            self.airports[row['iata_code']] = Airport(
                {key: value for key, value in row.items() if
                 key in airport_fields}
            )

        if len(self.airports.keys()) == 0:
            return False

        # destination airports
        uri = "http://localhost/aws/app/v1/games/" + self.game_id + "/airports"
        r = requests.get(uri)
        if r.status_code != 200:
            return False

        data = json.loads(r.text)['airports']
        # print("airports:\n{}".format(data))

        for row in data[0]['destinations']:
            if row['iata_code'] not in self.airports:
                self.airports[row['iata_code']] = Airport(
                    {key: value for key, value in row.items() if
                     key in airport_fields}
                )

        # fleet_types
        uri = "http://localhost/aws/app/v1/games/" + self.game_id + "/fleets"
        r = requests.get(uri)
        if r.status_code != 200:
            return False

        data = json.loads(r.text)['fleets']
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
        uri = "http://localhost/aws/app/v1/games/" + self.game_id + "/flights/basic"
        r = requests.get(uri)
        if r.status_code != 200:
            return False

        data = json.loads(r.text)['flights']
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
                    FlightCollection(self.shuffle_flights)
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

    def getTimetables(self):
        """loads flights and timetable data into a TimetableManager"""

        #cnx = pymysql.connect(user=self.db_user, password=self.db_pass,
        #                      host=self.db_host, db=self.db_name)
        #cursor = cnx.cursor(pymysql.cursors.DictCursor)

        timetables = {}
        tHdrs = {}

        # query = '''
        # SELECT timetable_id, timetable_name, fleet_type_id,
        # base_airport_iata,
        # TIME_FORMAT(base_turnaround_delta, '%H:%i') AS base_turnaround_delta
        # FROM timetables
        # WHERE game_id = {}
        # AND deleted = 'N'
        # '''.format(self.game_id)

        # cursor.execute(query)


        uri = "http://localhost/aws/app/v1/games/" \
              + self.game_id + "/timetables"
        r = requests.get(uri)
        if r.status_code != 200:
            return False

        self.timetables = {}

        data = json.loads(r.text)['timetables']

        # bomb successfully if no timetables found
        if len(data) == 0:
            return True

        for row in data:
            tHdrs[row['timetable_id']] = row
            if row['fleet_type_id'] not in self.fleet_types:
                print(row)

            # add airport and fleet-type objects
            tHdrs[row['timetable_id']]['fleet_type'] = (
                self.fleet_types[row['fleet_type_id']]
            )
            tHdrs[row['timetable_id']]['base_airport'] = (
                self.airports[row['base_airport_iata']]
            )

        # create an additional SQL condition for the timetable_ids we find
        # timetable_condition = ""
        # if len(tHdrs.keys()) > 0:
        #    timetable_condition = "AND t.timetable_id IN ({})".format(
        #        ", ".join(map(str, list(tHdrs.keys())))
        #        )

        r = requests.get(uri + "/" + ";".join(map(str, list(tHdrs.keys()))))
        if r.status_code != 200:
            return False

        data = json.loads(r.text)['timetables']

        for tt in data:
            timetable_id = tt['timetable_id']
            base_airport_iata = tHdrs[timetable_id]['base_airport'].iata_code
            fleet_type_id = tHdrs[timetable_id]['fleet_type'].fleet_type_id

            timetables[timetable_id] = Timetable(
                timetable_id=timetable_id,
                game_id=self.game_id,
                timetable_name=tHdrs[timetable_id]['timetable_name'],
                base_airport=tHdrs[timetable_id]['base_airport'],
                fleet_type=tHdrs[timetable_id]['fleet_type'],
                outbound_dep=tt["entries"][0]['start_time'],
                fManager=self.ttManager,
                base_turnaround_delta=tHdrs[timetable_id]['base_turnaround_delta'])

            for row in tt["entries"]:
                # flight_lookup fails for MTX
                # dest_turnaround is bogus
                dt = (str_to_timedelta(row['dest_turnaround_padding']) +
                      tHdrs[timetable_id]['fleet_type'].ops_turnaround_length)
                if row['flight_number'] == 'MTX':
                    flight = self.MTXFlights[base_airport_iata][fleet_type_id]
                else:
                    flight = self.flight_lookup[row['flight_number']][
                        fleet_type_id]
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
            self.ttManager.append(timetables[id])

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

    def getRandomStartTime(self, base_airport_iata):
        retVal = None
        random.seed()
        base_airport = self.airports[base_airport_iata]
        while retVal is None:
            retVal = nptime(5, 30) + \
                     timedelta(seconds=random.randrange(0, 216) * 300)
            if base_airport.in_curfew(retVal) or OpTimes.InDepCurfew(retVal):
                print("Bad start time {}".format(retVal))
                retVal = None

        return retVal

    def add_flight(self, tt, ttManager):
        if tt.is_good(self.threshold):
            return tt

        # if the tt size exceeds the maximum, spit back nothing
        if (tt.total_time().total_seconds() > 7 * 86400):
            return None

        # print(tt)

        fltCln = (
            self.flights[tt.base_airport.iata_code][
                tt.fleet_type.fleet_type_id]
        )

        t2 = None
        for f in fltCln:
            # reject flights which would make timetable longer than 1 week
            if (tt.total_time() + f.length()).total_seconds() > 7 * 86400:
                continue
            if not ThreadController.running():
                # pdb.set_trace()
                ThreadController.reset()
                return None

            if tt.isEmpty():
                # pass
                # pdb.set_trace()
                print("Starting timetable with {}".format(str(f)))
            # pdb.set_trace()
            entry = TimetableEntry(f, tt)

            if not entry.is_good():
                continue

            newTT = tt + entry
            # print(newTT)

            # import pdb; pdb.set_trace()

            # ignore already rejected combinations
            if self.use_rejected and newTT.lex() in self.rejected:
                # print("Rejecting [{}]".format(newTT.lex()))
                continue

            fltCln.delete(f)
            ttManager.append(entry)
            t2 = self.add_flight(newTT, ttManager)
            if t2:
                break
            else:
                fltCln.undelete(f)
                ttManager.remove(entry)
                self.rejected.append(newTT.lex())
                # print("Rej: [{}] = [{}]".format(newTT.seq(), newTT.lex()))

        return t2

    def __call__(self, base_airport_iata, fleet_type_id, start_time,
                 base_turnaround_delta=None, threshold=0.95, rebuild=False,
                 count=1, max_range=None, exclude_flights=None,
                 writeToDB=False, ignore_base_timetables=False,
                 add_mtx_gap=False, graveyard=True, jsonDir=None):
        """verify args"""

        if (base_airport_iata not in self.flights
            or fleet_type_id not in self.flights[base_airport_iata]):
            raise Exception("__call__ args: base_airport_iata = {}; "
                            "fleet_type_id = {}".format(base_airport_iata,
                                                        fleet_type_id))

        if not str_to_nptime(start_time):
            start_time = self.getRandomStartTime(base_airport_iata)
            # raise Exception("__call__ args: start_time={}".format(start_time))

        if threshold < 0.90 or threshold > 1.0:
            raise Exception(
                "Bad threshold for TimetableBuilder: {}".format(threshold))

        self.threshold = threshold

        # check whether given start time is feasible
        # start time[0] = earliest_available[last]

        # modify maintenance flight to include turnaround
        mtx = self.MTXFlights[base_airport_iata][fleet_type_id]
        mtx.hasBaseTurnaround = add_mtx_gap

        # if ignore_base_timetables is set, we disregard timetables from this
        # base when doing conflict checks
        self.ttManager.setIgnoreBaseTimetables(ignore_base_timetables)

        all_timetables = []

        fltCln = self.flights[base_airport_iata][fleet_type_id]

        # a single flight number may be operated by multiple fleet_types;
        # remove all timetabled flights in other fleet_type_id values
        # print(self.timetables[base_airport_iata])
        if base_airport_iata in self.timetables.keys():
            flTypes = filter(lambda q: q != fleet_type_id,
                             self.timetables[base_airport_iata].keys())
            for f in flTypes:
                for x in self.timetables[base_airport_iata][f]:
                    for e in x.flights:
                        if e.flight.flight_number != "MTX":
                            # print("Deleting "+str(e.flight))
                            fltCln.deleteByFlightNumber(e.flight.flight_number)

        ttMgr = self.ttManager

        # if rebuild is not set, we remove timetabled flights from fltCln
        if (not rebuild
            and base_airport_iata in self.timetables
            and fleet_type_id in self.timetables[base_airport_iata]):
            print("Deleting {}, {} from fltCln".format(base_airport_iata,
                                                       fleet_type_id))
            for ttObj in self.timetables[base_airport_iata][fleet_type_id]:
                for ttEntryObj in ttObj.flights:
                    fltCln.delete(ttEntryObj.flight)
        else:
            fltCln.reset()

            # create our filtered TimetableManager, excluding the flights from
            # this base/fleet type
            ttMgr = self.ttManager.filter(base_airport_iata, fleet_type_id)

        # if a list of excluded flight numbers is supplied, we delete them from
        # the FlightCollection
        if isinstance(exclude_flights, list):
            exclude_flights = [s.upper() for s in exclude_flights]
            for x in exclude_flights:
                if (x != 'MTX'
                    and x in self.flight_lookup
                    and fleet_type_id in self.flight_lookup[x]):
                    print("Excluding {}".format(
                        self.flight_lookup[x][fleet_type_id]))
                    fltCln.delete(self.flight_lookup[x][fleet_type_id])

        tt = Timetable(None, self.game_id, None,
                       self.airports[base_airport_iata],
                       self.fleet_types[fleet_type_id], start_time,
                       ttMgr, base_turnaround_delta, max_range)
        tt.graveyard = graveyard

        # not seen at this time vv
        retryCount = 0
        old_index = 0
        index = 1
        while True:
            print("Using start time {}".format(tt.available_time))
            TimeLimit = 10.0  # * index

            fib = old_index
            old_index = index
            index = old_index + fib

            if retryCount > 4000:
                print("No more!")
                break

            print("Running for max {} s; len(all_timetables) = {}".format(
                TimeLimit, len(all_timetables)))

            if fltCln.total_time().total_seconds() < 6 * 86400:
                print(
                    "Less than 7 days flights remain {} - terminating".format(
                        fltCln.total_time()))
                break

            ThreadController.start(TimeLimit)

            print("Before: {} entries; {}".format(len(fltCln),
                                                  fltCln.total_time()))
            self.rejected = []
            newTimetable = self.add_flight(tt, ttMgr)

            ThreadController.stop()

            # print(newTimetable)
            if newTimetable:
                print("After: {} entries; {}\n".format(len(fltCln),
                                                       fltCln.total_time()))
                all_timetables.append(newTimetable)
                fltCln.releaseMTX()

                if count > 0 and len(all_timetables) >= count:
                    break
                else:
                    # tt.available_time += timedelta(minutes=5)
                    tt.available_time = self.getRandomStartTime(
                        base_airport_iata)
                    # print(str(x))
            else:
                if not self.shuffle_flights:
                    print("Aborting - all possible options exhausted")
                    break

                retryCount += 1

                if len(all_timetables) > 0:
                    c = random.randint(1, len(all_timetables))
                    print(
                        "Deleting {} timetables and starting again".format(c))
                    for i in range(0, c):
                        # delete the last timetable from the list
                        deleted = all_timetables.pop()

                        # the flights can no longer be used for conflict checks
                        ttMgr.remove(deleted)

                        # remove the flights from the flight collection
                        for x in deleted.flights:
                            fltCln.undelete(x.flight)

                # now we can restart the process from the index-1 th timetable
                # tt.available_time = str_to_nptime(start_time)



                # print("Removing all timetables and starting again\n")
                tt.available_time = self.getRandomStartTime(base_airport_iata)

                if (index >= 2):
                    index = old_index = 1

        if (base_airport_iata in self.timetables 
            and fleet_type_id in self.timetables[base_airport_iata]):
            count = len(self.timetables[base_airport_iata][fleet_type_id])
        else:
            count = 0
                    
        out = []
        for a in all_timetables:
            # increment name            
            if a.timetable_name is None:
                a.timetable_name = "%s-%s-%02d" % (base_airport_iata,
                                                    a.fleet_type.fleet_icao_code,
                                                    count + 1)
                count = count + 1
            out.append(a.to_json())
            print(str(a))
            if writeToDB:
                self.writeTimetableToDB(a)
        # ttManager.remove(tt)

        # write JSON to file
        if jsonDir is not None:
            filename = jsonDir + "/" +  base_airport_iata + "-" + \
                       self.fleet_types[fleet_type_id].fleet_icao_code + "-" + \
                       str(id(out)) + ".json"

            f = open(filename, 'w')
            f.write("[" + ",\n".join(out) + "]")
            f.close()

        print(fltCln.status())
        # fltCln.reset()
        # print(fltCln.status())

    def writeTimetableToDB(self, tt):
        if not isinstance(tt, Timetable):
            raise Exception("Bad args for writeTimetableToDB")

        cnx = connector.connect(user=self.db_user, password=self.db_pass,
                                host=self.db_host, database=self.db_name)
        cursor = cnx.cursor(dictionary=True, buffered=True)

        # this might be the first timetable of this type at this base
        fleet_type_id = tt.fleet_type.fleet_type_id
        base_airport_iata = tt.base_airport.iata_code
        if base_airport_iata not in self.timetables:
            self.timetables[base_airport_iata] = {}
        if fleet_type_id not in self.timetables[base_airport_iata]:
            self.timetables[base_airport_iata][fleet_type_id] = []

        if tt.timetable_name is None:
            if base_airport_iata in self.timetables:
                count = len(self.timetables[base_airport_iata][fleet_type_id])
            else:
                count = 0
                                                       
            tt.timetable_name = "%s-%s-%02d" % (base_airport_iata,
                                                tt.fleet_type.fleet_icao_code,
                                                count + 1)

        query = '''
        INSERT INTO timetables (game_id, base_airport_iata, fleet_type_id, 
        timetable_name, base_turnaround_delta, entries_json, last_modified)
        VALUES ({}, '{}', {}, '{}', '{}', '{}', NOW())
        '''.format(self.game_id, base_airport_iata, fleet_type_id,
                   tt.timetable_name,
                   timedelta_to_hhmm(tt.base_turnaround_length -
                                     tt.fleet_type.min_turnaround),
                   tt.to_json())

        # print(query)
        cursor.execute(query)

        tt.timetable_id = cursor.lastrowid

        # timetable_entries rows
        entries = []

        # any required changes to flights.turnaround_length
        flight_updates = {}

        for x in tt.flights:
            txt = "({}, '{}', '{}', '{}', '{}', '{}', '{}')".format(
                tt.timetable_id, x.flight.flight_number,
                x.flight.dest_airport.iata_code,
                x.outbound_dep.strftime("%H:%M"),
                x.start_day, x.available_time.strftime("%H:%M"),
                timedelta_to_hhmm(x.post_padding)
            )
            entries.append(txt)

            # save adjusted dest_turnaround_paddings
            if x.dest_turnaround_padding != x.flight.turnaround_length:
                flight_updates[x.flight.flight_number] = (
                    "WHEN '{}' THEN '{}' ".format(
                        x.flight.flight_number,
                        timedelta_to_hhmm(x.dest_turnaround_padding)
                    ))

        query = '''
        INSERT INTO timetable_entries (timetable_id, flight_number, 
        dest_airport_iata, start_time, start_day, earliest_available, post_padding)
        VALUES {}
        '''.format(", ".join(entries))
        # print(query)

        cursor.execute(query)

        # update flights with new destination turnarounds if required
        if len(flight_updates):
            query = '''
            UPDATE flights
                SET turnaround_length = CASE flight_number
                {}
                END
            WHERE game_id = {}
            AND deleted = 'N'
            AND flight_number IN ('{}')
            '''.format(
                "\n ".join(list(flight_updates.values())),
                self.game_id,
                "', '".join(list(flight_updates.keys())),
            )

            print(query)
            # cursor.execute(query)

        if cnx.in_transaction:
            cnx.commit()
        cursor.close()
        cnx.close()

        self.timetables[base_airport_iata][fleet_type_id].append(tt)

        print("Added timetable [{}] to DB".format(tt.timetable_name))
