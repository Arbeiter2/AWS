from controller import Controller, rest_controller
import simplejson as json
from decimal import Decimal
from nptime import nptime
from datetime import datetime, timedelta
from collections import OrderedDict
from aws_flights import validateTime
import re

def str_to_timedelta(hhmmss):
    """converts string of format HH:MM:SS to timedelta object, excluding seconds"""
    if isinstance(hhmmss, timedelta):
        return hhmmss

    if not hhmmss:
        return None
    
    try:
        hh,mm = hhmmss.split(":")[0:2]
        return timedelta(hours=int(hh), minutes=int(mm))
    except ValueError:
        return None

def str_to_nptime(hhmmss):
    """converts string of format HH:MM:SS to nptime object, excluding seconds"""
    if isinstance(hhmmss, nptime):
        return hhmmss

    if not hhmmss:
        return None
    
    try:
        hh,mm = hhmmss.split(":")[0:2]
        return nptime(hour=int(hh), minute=int(mm))    
    except ValueError:
        return None

def time_to_str(obj):
    if isinstance(obj, nptime):
        obj = obj.to_timedelta()
    
    return timedelta_to_hhmm(obj)

def timedelta_to_hhmm(td):
    if not isinstance(td, timedelta):
        return ""
    else:
        total = td.total_seconds()
        return "%02d:%02d" % (total//3600, total%3600//60)

airport = re.compile(r"^[A-Z]{3}$")
num = re.compile(r"^\d+$")

"""manages CRUD ops on Timetables"""
class Timetables(Controller):
    def get(self):
        """calls appropriate handler based on self.urlvars"""
        # mandatory
        game_id = int(self.urlvars.get('game_id', None))
        
        # for getting arbitrary flights
        base_airport_iata = self.urlvars.get('base_airport_iata', None)
        dest_airport_iata = self.urlvars.get('dest_airport_iata', None)
        timetable_id = self.urlvars.get('timetable_id', None)
        fleet_type_id = self.urlvars.get('fleet_type_id', None)
        flight_number = self.urlvars.get('flight_number', None)
        mode = self.urlvars.get('mode', None)
        
        conflicts = False
        if (re.search('\/conflicts\/', self.request.path) is not None):
            conflicts = True

        # remove trailing slashes from PATH_INFO
        #path = re.sub(r"\/+$", "", self.request.path)
        
        # if we get /flights, we return basic data for assigned flights
        #assigned_only = path.split("/")[-1:][0] == 'flights'
        assigned_only = (mode == 'flights')
        all_data = (mode == 'all')
        
        if game_id is None:
            # bad request; missing game_id and/or other vars
            return self.error(400)
        elif conflicts:
            return self.conflicts(game_id, base_airport_iata, timetable_id)
        elif assigned_only:
            return self.getAssignedFlights(game_id)
        elif (timetable_id or all_data):
            return self.getTimetables(game_id, base_airport_iata, 
                fleet_type_id, timetable_id, all_data)
        elif flight_number or dest_airport_iata:
            return self.searchTimetables(game_id, flight_number,
                                         dest_airport_iata)
        else:
            return self.getTimetableHeaders(game_id, base_airport_iata,
             fleet_type_id)

    def getFleetTypes(self):
        self.fleet_type_map = {}

        query = "SELECT * FROM fleet_types"

        cursor = self.get_cursor()
        cursor.execute(query)

        for row in cursor:
            self.fleet_type_map[row['fleet_type_id']] = row
            
    '''return a list of timetables containing the specified flight_number'''
    def searchTimetables(self, game_id, flight_number, dest_airport_iata):
        if game_id is None or (not flight_number and not dest_airport_iata):
            return self.error(500)
            
        param = None
        if dest_airport_iata:
            param = 'te.dest_airport_iata'
            elems = list(set(re.split("[;,]", dest_airport_iata)))
        else:
            #param = 'flight_number'
            #elems = list(set(re.split("[;,]", flight_number)))
            
            # we only use 2-char IATA airline code
            param = 'CAST(f.number AS CHAR)'
            elems = list(set(map(lambda x: str(int(x[2:])), 
                                 re.split("[;,]", flight_number))))
        query = '''
        SELECT DISTINCT t.game_id, te.timetable_id, te.dest_airport_iata,
        t.base_airport_iata, t.timetable_name, t.fleet_type_id, 
        ft.icao_code AS fleet_type, te.flight_number, te.start_time,
        te.start_day
        FROM timetable_entries te, timetables t, fleet_types ft, 
        flights f, routes r
        WHERE t.game_id = {}
        AND f.game_id = t.game_id
        AND f.route_id = r.route_id
        AND r.dest_airport_iata = te.dest_airport_iata
        AND t.timetable_id = te.timetable_id
        AND f.number = CAST(SUBSTR(te.flight_number, 3) AS DECIMAL)
        AND {} IN ('{}')
        AND ft.fleet_type_id = t.fleet_type_id
        AND f.fleet_type_id = t.fleet_type_id
        AND t.deleted = 'N'
        AND f.deleted = 'N'
        '''.format(game_id, param, "', '".join(elems))
        #print(query)
        
        cursor = self.get_cursor()
        cursor.execute(query)
        if cursor.rowcount <= 0:
            return self.error(404)
        
        fields = ["game_id", "timetable_id", "timetable_id_href", 
            "timetable_name", "fleet_type_id", 
            'fleet_type', 'fleet_type_href',
            'flight_number', 'flight_number_href',
            "base_airport_iata", "base_airport_iata_href",
            "dest_airport_iata", "dest_airport_iata_href",
            "start_time", "start_day"]
        
        output = []
        for row in cursor:
            bits = str(row['start_time']).split(':')[:2]
            if len(bits[0]) == 1:
                bits[0] = "0" + bits[0]
            row['start_time'] = ":".join(bits)
            row['fleet_type_href'] = "{}/fleets/{}.{}".format(
                self.request.application_url, row['fleet_type_id'], 
                self.content_type)
            
            row['timetable_id_href'] = "{}/games/{}/timetables/{}.{}".format(
                self.request.application_url, row['game_id'],
                row['timetable_id'], self.content_type)

            row['flight_number_href'] = "{}/games/{}/flights/{}.{}".format(
                self.request.application_url, row['game_id'],
                row['flight_number'], self.content_type)
                
            row['base_airport_iata_href'] = "{}/airports/{}.{}".format(
                self.request.application_url, row['base_airport_iata'], 
                self.content_type)

            row['dest_airport_iata_href'] = "{}/airports/{}.{}".format(
                self.request.application_url, row['dest_airport_iata'], 
                self.content_type)
                
            output.append(OrderedDict((key, row[key]) for key in fields))   
        
        self.html_template = [{ "table_name" : "timetable flight search",
        "entity" : "timetable",
            "fields" : ["game_id", "timetable_id", "timetable_name", 
            'fleet_type', "flight_number",
            "base_airport_iata", 'dest_airport_iata', "start_day", 
            "start_time"
             ] }]

        self.resp_data = { "timetable flight search" : output }
        
        return self.send()   
        
        
    def getTimetableHeaders(self, game_id, base_airport_iata, fleet_type_id):
        """retrieves summary data for all timetables """
        base_condition = ""
        fleet_condition = ""
        if (base_airport_iata is not None):
            base_condition = "AND (t.base_airport_iata = '{}')".format(
                base_airport_iata)
        
        if (fleet_type_id is not None):
            fleet_condition = "AND (t.fleet_type_id = '{}')".format(
                fleet_type_id)

        self.getFleetTypes()
                
        last_modified = datetime(1970, 1, 1)
        query = '''
        SELECT t.game_id, t.timetable_id, last_modified, timetable_name, 
        t.fleet_type_id, r.base_airport_iata, 
        TIME_FORMAT(base_turnaround_delta, '%H:%i') AS base_turnaround_delta,
        MAX(distance_nm) AS max_distance_nm
        FROM timetables t, timetable_entries te, flights f, routes r
        WHERE t.game_id = {}
        AND t.game_id = f.game_id
        AND f.flight_number = te.flight_number
        AND r.route_id = f.route_id
        AND t.deleted = 'N'
        AND f.deleted = 'N'
        AND t.timetable_id = te.timetable_id
        {} {}
        GROUP BY timetable_id
        ORDER BY fleet_type_id, timetable_name
        '''.format(game_id, base_condition, fleet_condition)
        
        #print(query)
    
        cursor = self.get_cursor()
        cursor.execute(query)
        if cursor.rowcount <= 0:
            self.resp_data = { "timetables" : [] }
            return self.send()
        
        fields = ["game_id", "timetable_id", "timetable_id_href", 
            "timetable_name", "fleet_type_id", "max_distance_nm",
            'fleet_type', 'fleet_type_href', 'base_turnaround_delta',
            "base_airport_iata", "base_airport_iata_href"]
        
        output = []
        for row in cursor:
            row['fleet_type_href'] = "{}/fleets/{}.{}".format(
                self.request.application_url, row['fleet_type_id'], 
                self.content_type)
            row['fleet_type'] = self.fleet_type_map[row['fleet_type_id']]["icao_code"]
            
            row['timetable_id_href'] = "{}/games/{}/timetables/{}.{}".format(
                self.request.application_url, row['game_id'],
                row['timetable_id'], self.content_type)

            row['base_airport_iata_href'] = "{}/airports/{}.{}".format(
                self.request.application_url, row['base_airport_iata'], 
                self.content_type)
            
            if row['last_modified'] > last_modified:
                last_modified = row['last_modified']
            output.append(OrderedDict((key, row[key]) for key in fields))

        #self.resp.text = json.dumps(output)
        
        self.html_template = [{ "table_name" : "timetables",
        "entity" : "timetable",
            "fields" : ["game_id", "timetable_id", "base_airport_iata",
            "timetable_name", 'fleet_type', 'base_turnaround_delta',
            'max_distance_nm'] }]

        self.resp_data = { "timetables" : output }
        self.resp.last_modified = last_modified.timestamp()
        
        return self.send()        

    def getTimetables(self, game_id, base_airport_iata, fleet_type_id, 
        timetable_id, all_data):
        """return an array of timetable objects""" 
        
        if (game_id is None
        or (timetable_id is None 
        and base_airport_iata is None
        and fleet_type_id is None
        and not all_data)):
            self.resp_data = { "timetables" : [] }
            return self.send()
            
        timetables = {}
        
        condition = ""
        # we get either flight or flight_number, and bomb if neither is found
        if (timetable_id is not None):
            # fail for any non-numeric timetable_id
            if any(num.match(id) is None for id in timetable_id.split(";")):
                return self.error(400)
            condition += "AND (timetable_id IN ({}))".format(
                ", ".join(timetable_id.split(";")))
        elif (base_airport_iata is not None):
            condition += "AND (base_airport_iata = '{}')".format(base_airport_iata)
        elif fleet_type_id is not None:
            condition += "AND (fleet_type_id = {})".format(fleet_type_id)
        elif all_data:
            condition = ""
    
        self.getFleetTypes()
        

        # find top-level data first
        last_modified = datetime.today()
        query = """
        SELECT game_id, timetable_id, last_modified, timetable_name, 
        fleet_type_id, base_airport_iata, 
        TIME_FORMAT(base_turnaround_delta, '%H:%i') AS base_turnaround_delta
        FROM timetables
        WHERE game_id = {}
        AND deleted = 'N'
        {}
        """.format(game_id, condition)
        
        cursor = self.get_cursor()
        cursor.execute(query)
        if cursor.rowcount <= 0:
            return self.error(404)


        timetable_fields = ["game_id", "timetable_id", "timetable_id_href", 
            "timetable_name", "fleet_type_id", "fleet_type",
            "fleet_type_href", "base_airport_iata", 
            "base_airport_iata_href", "base_turnaround_delta", "entries"]        

        for row in cursor:
            row['entries'] = []
            # add resource locator for base airport
            row['base_airport_iata_href'] = "{}/airports/{}.{}".format(
                self.request.application_url, row['base_airport_iata'],
                self.content_type)

            # fleet type ICAO code
            row['fleet_type'] = self.fleet_type_map[row['fleet_type_id']]["icao_code"]
            row['fleet_type_href'] = "{}/fleets/{}.{}".format(
                self.request.application_url, row['fleet_type_id'], 
                self.content_type)
        
            row['timetable_id_href'] = "{}/games/{}/timetables/{}.{}".format(
                self.request.application_url,  game_id, row['timetable_id'], 
                self.content_type)

            t = OrderedDict((key, row[key]) for key in timetable_fields)
            timetables[str(row['timetable_id'])] = t
            
            # newest entry is last modified
            if (row['last_modified'] is not None
                and row['last_modified'] > last_modified):
                last_modified = row['last_modified']
                
            

        # if any of the requested timetable_ids is missing, fail
        if (timetable_id and
        any(x not in timetables for x in timetable_id.split(";"))):
            return self.error(404)
        
        # create an additional SQL condition for the timetable_ids we find
        timetable_condition = "AND t.timetable_id IN ({})".format(
                ", ".join(map(str, list(timetables.keys()))))

        # find route distances
        routes = dict()
        query = '''
        SELECT base_airport_iata, dest_airport_iata, 
        distance_nm
        FROM routes r
        WHERE game_id = {}
        '''.format(game_id)
        cursor.execute(query)
        for row in cursor:
            key = "{}-{}".format(row['base_airport_iata'],
                                    row['dest_airport_iata'])
            routes[key] = row['distance_nm']

        query = '''
        SELECT DISTINCT t.timetable_id, e.flight_number, t.base_airport_iata,
        e.dest_airport_iata, t.fleet_type_id,
        e.start_day, TIME_FORMAT(e.start_time, '%H:%i') AS start_time,
        TIME_FORMAT(e.post_padding, '%H:%i') AS post_padding,
        TIME_FORMAT(e.dest_turnaround_padding, '%H:%i') AS dest_turnaround_padding,
        TIME_FORMAT(e.earliest_available, '%H:%i') AS earliest_available
        FROM timetables t, timetable_entries e
        WHERE t.timetable_id = e.timetable_id
        {}
        AND t.deleted = 'N'
        ORDER BY t.timetable_id, start_day, start_time
        '''.format(timetable_condition)
        #print(query)
        cursor.execute(query)
 
        entry_fields = ["flight_number", "flight_number_href",
            "dest_airport_iata", "dest_airport_iata_href", "distance_nm", 
            "start_day", "start_time", "dest_turnaround_padding", 
            "post_padding", "earliest_available"]
        for row in cursor:
            if not (row['flight_number'] == 'MTX'):
                key = "{}-{}".format(row['base_airport_iata'],
                                        row['dest_airport_iata'])
                row['distance_nm'] = routes[key]
            else:
                row['distance_nm'] = 0

            timetable_id = str(row['timetable_id'])
            # add resource locator for base/destination airports
            row['flight_number_href'] = "{}/games/{}/flights/{}.{}".format(
                self.request.application_url, game_id, row['flight_number'], 
                self.content_type)
            row['dest_airport_iata_href'] = "{}/airports/{}.{}".format(
                self.request.application_url, row['dest_airport_iata'], 
                self.content_type)

            e = OrderedDict((k, row[k]) for k in entry_fields)
            timetables[timetable_id]['entries'].append(e)
            
                
        
        self.html_template = [{ "table_name" : "timetables", 
            "entity" : "timetable",
            "fields" : ["game_id", "timetable_id", "timetable_name", 
            "fleet_type", "base_airport_iata", "base_turnaround_delta", 
            { "table_name" : "entries", "entity" : "timetable_entry",
            "fields" : ["flight_number", "dest_airport_iata", "distance_nm",
            "start_day", "start_time", "dest_turnaround_padding", 
            "post_padding", "earliest_available"] }],
            "stacked_headers" : True }]
            
        self.resp_data = { "timetables" : list(timetables.values()) }
        #self.resp.text = json.dumps(list(timetables.values()))
        self.resp.last_modified = last_modified.timestamp()
        
        return self.send()

    def getAssignedFlights(self, game_id):
        cursor = self.get_cursor()

        # mandatory
        game_id = self.urlvars.get('game_id', None)
        if (game_id is None):
            # bad request; missing game_id and/or other vars
            return self.error(400)

        self.getFleetTypes()

        query = """
        SELECT DISTINCT t.last_modified, f.number, 
        te.flight_number, t.base_airport_iata, t.fleet_type_id, 
        te.dest_airport_iata, te.timetable_id
        FROM timetables t, timetable_entries te, flights f
        WHERE t.game_id = {}
        AND f.game_id = t.game_id
        AND f.flight_number = te.flight_number
        AND t.timetable_id = te.timetable_id
        AND t.deleted = 'N'
        AND f.deleted = 'N'
        AND te.flight_number <> 'MTX'
        ORDER BY number""".format(game_id)
        cursor.execute(query)
        
        rows = cursor.fetchall()
        if (len(rows) == 0):
            self.resp_data = { "flights" : [] }
            return self.send()
            
        # get latest last_modified of all timetables
        last_modified = datetime(1970, 1, 1)
        out = []
        fields = ["flight_number", "flight_number_href", "base_airport_iata", 
            "base_airport_iata_href",  "fleet_type_id", 
            "fleet_type", "fleet_type_href", 
            "dest_airport_iata", "dest_airport_iata_href",
            "timetable_id", "timetable_id_href",]
        
        for r in rows:
            last_modified = max([r['last_modified'], last_modified])
        
            r['flight_number_href'] = "{}/games/{}/flights/{}.{}".format(
                self.request.application_url, game_id, r['flight_number'], 
                self.content_type)
                
            r['fleet_type_href'] = "{}/fleets/{}.{}".format(
                self.request.application_url, r['fleet_type_id'], 
                self.content_type)
            r['fleet_type'] = self.fleet_type_map[r['fleet_type_id']]["icao_code"]
            
            r['base_airport_iata_href'] = "{}/airports/{}.{}".format(
                self.request.application_url, r['base_airport_iata'], 
                self.content_type)

            r['dest_airport_iata_href'] = "{}/airports/{}.{}".format(
                self.request.application_url, r['dest_airport_iata'], 
                self.content_type)

            r['timetable_id_href'] = "{}/games/{}/timetables/{}.{}".format(
                self.request.application_url, game_id, r['timetable_id'], 
                self.content_type)
                
            out.append(OrderedDict((key, r[key]) for key in fields))
                
                
        #self.resp.text = json.dumps(rows)
        self.html_template = [{ "table_name" : "flights",
            "entity" : "flight",
            "fields" : ["flight_number", "base_airport_iata", 
            "fleet_type", "dest_airport_iata", "timetable_id", ]}]
        self.resp_data = { "flights" : out }

        self.resp.last_modified = last_modified.timestamp()
        self.resp.status = 200

        return self.send()
        
    def delete(self):
        """calls appropriate handler based on self.urlvars"""
        cursor = self.get_cursor()

        # mandatory
        game_id = self.urlvars.get('game_id', None)

        base_airport_iata = self.urlvars.get('base_airport_iata', None)
        timetable_id = self.urlvars.get('timetable_id', None)
        fleet_type_id = self.urlvars.get('fleet_type_id', None)

        if (game_id is None):
            # bad request; missing game_id and/or other vars
            return self.error()

        if timetable_id is not None:
            # fail for any non-numeric timetable_id
            if any(num.match(id) is None for id in timetable_id.split(";")):
                return self.error()
            condition = "AND timetable_id IN ({})".format(
                ", ".join(timetable_id.split(";")))        
        elif base_airport_iata is not None:
            if airport.match(base_airport_iata) is None:
                return self.error()
                
            condition = "AND base_airport_iata = '{}'".format(base_airport_iata)

            # additional fleet_type_id condition, only to permit DELETE for
            # /base_airport_iata/fleet_type_id
            if fleet_type_id is not None:
                if int(fleet_type_id) <= 0:
                    return self.error()
                condition += "\nAND fleet_type_id = {}".format(fleet_type_id)
                
        query = """
            UPDATE timetables
            SET deleted = 'Y'
            WHERE game_id = {}
            {}""".format(game_id, condition)
        cursor.execute(query)
        if (cursor.rowcount <= 0):
            return self.error(404)
        else:
            #pass
            self.db.commit()
        
        self.resp.status = 200
        return self.send()        

    """
    internal function for performing conflict checks
    """    
    def getConflicts(self, flight1, flight2, minimum_gap):
        fields = None
        output = []
        
        #print(flight1, flight2)
        
        # fields is a list of pairs of values to compare;
        # for flights with identical base and destination,
        # compare out/inbound times together;
        # for flights where base and destination are mirror images,
        # compare inbound of flight1 with outbound of flight2 etc.
        if (flight1['base_airport_iata'] == flight2['base_airport_iata']
        and flight1['dest_airport_iata'] == flight2['dest_airport_iata']):
            fields = [('outbound_dep_time', 'outbound_dep_time'),
                      ('inbound_dep_time', 'inbound_dep_time')]
        elif (flight1['base_airport_iata'] == flight2['dest_airport_iata']
        and flight1['base_airport_iata'] == flight2['dest_airport_iata']):
            fields = [('outbound_dep_time', 'inbound_dep_time'),
                      ('inbound_dep_time', 'outbound_dep_time')]
        else:
            # flights cannot be compared
            return output

        for time in fields:
            # if the difference between the two times  
            # exceeds 12 hours, we subtract it from 24 hours
            diff = (flight1[time[0]] - flight2[time[1]])
            if (diff.seconds > 12 * 3600): # 12 hours
                diff = timedelta(seconds=86400 - diff.seconds)
            
            if (diff.seconds >= minimum_gap):
                continue
                
            a = dict()
            a['event'] = "{}/{}".format(time[0], time[1])
            # inbound_dep_time/outbound_dep_time
            a['flights'] = [flight1['flight_number'], 
                            flight2['flight_number']]
            a['times'] = [
                time_to_str(flight1[time[0]]),
                time_to_str(flight2[time[1]])
            ]
            a['timetable_id'] = [
                flight1['timetable_id'], 
                flight2['timetable_id']
            ]
            a['timetable_name'] = [
                flight1['timetable_name'], 
                flight2['timetable_name']
            ]
            output.append(a)

        return output

    
    """
    checks inbound and outbound flights from base_airport_iata for flights 
    to a destination which are less than threshold minutes apart. 
    Use provided timetable_id list if provided, or check all timetables.
    returns an array of objects containing pairs of flights with conflicting 
    departure times, either inbound or outbound; they are grouped by destination
    with details of each problematic pair
    
    {
        "SJU":
        [
            {
                "event": "inbound_dep_time",
                "dest": "DFW",
                "flights": ["QV203", "QV902"],
                "times": ["10:50", "11:05"],
                "timetable_id": ["917", "845"]
            },
            ...
        ],
        
        "LAX":
        [
        ...
        ],
        ....
    }
 
    replaces conflicts.php
    """
    def conflicts(self, game_id, base_airport_iata, timetable_id):
        if game_id is None:
            return self.error(500)
            
        self.pairsChecked = []

        timetable_id_list = None
        bid = ""        
        if base_airport_iata is not None:
            if not airport.match(base_airport_iata):
                return self.error(500)
            else:
                bid= [base_airport_iata]
        elif timetable_id is not None:        
            if any(num.match(id) is None for id in timetable_id.split(";")):
                return self.error(500)
            else:
                bid = []
                timetable_id_list = timetable_id.split(";")
                query = """
                SELECT DISTINCT base_airport_iata
                FROM timetables t
                WHERE t.game_id = '{}'
                AND deleted = 'N'
                AND timetable_id IN ({})
                """.format(game_id, ", ".join(timetable_id_list))

                cursor = self.get_cursor()
                cursor.execute(query)
                for row in cursor:
                    bid.append(row['base_airport_iata'])
                if len(bid) == 0:
                    return self.error(500)
        else:
            return self.error(500)
            
        bidlist = "', '".join(bid)
        
        
        flight_data = dict()
        
        
        query = """
        SELECT t.timetable_name, t.timetable_id, t.fleet_type_id, 
        te.flight_number, t.base_airport_iata, te.dest_airport_iata,
        TIME_FORMAT(te.start_time, '%H:%i') AS start_time 
        FROM timetables t, timetable_entries te 
        WHERE game_id = '{}' 
        AND t.timetable_id = te.timetable_id 
        AND t.deleted = 'N' 
        AND te.flight_number <> 'MTX'
        AND (t.base_airport_iata IN ('{}')
        OR te.dest_airport_iata IN ('{}'))
        """.format(game_id, bidlist, bidlist)
        
        #print(query)
        
        cursor = self.get_cursor()
        cursor.execute(query)
        if cursor.rowcount <= 0:
            return self.error(404)

        for row in cursor:
            f = dict()
            
            if row['dest_airport_iata'] == 'MTX':
                continue
            
            f['base_airport_iata'] = row['base_airport_iata']
            f['dest_airport_iata'] = row['dest_airport_iata']
            f['flight_number'] = row['flight_number']
            #f['fleet_type'] = row['fleet_type'];
            f['fleet_type_id'] = row['fleet_type_id']
            f['timetable_id'] = row['timetable_id']
            f['timetable_name'] = row['timetable_name']
            f['start'] = row['start_time']
            
            if row['base_airport_iata'] not in flight_data:
                flight_data[row['base_airport_iata']]= dict()
                
            if (row['dest_airport_iata'] not in 
                flight_data[row['base_airport_iata']]):
                flight_data[row['base_airport_iata']][row['dest_airport_iata']
                ] = dict()

            flight_data[row['base_airport_iata']][row['dest_airport_iata']][
                row['flight_number']] = f

        multiples = dict()
        m = []

        # find all destinations with more than one flight
        for base in flight_data:
            multiples[base] = dict()
            for dest in flight_data[base]:
                if len(flight_data[base][dest]) <= 1:
                    continue

                multiples[base][dest] = dict()
                
                #print(base, dest, flight_data[base][dest])

                for q in flight_data[base][dest].values():
                    multiples[base][dest][q['flight_number']] = zed = dict()
                    zed['flight_number'] = q['flight_number']
                    zed['base_airport_iata'] = q['base_airport_iata']
                    zed['dest_airport_iata'] = q['dest_airport_iata']
                    zed['fleet_type_id'] = q['fleet_type_id']
                    zed['timetable_id'] = q['timetable_id']
                    zed['timetable_name'] = q['timetable_name']

                    zed['outbound_dep_time'] = str_to_nptime(
                        flight_data[base][dest][q['flight_number']]['start'])
                    m.append(q['flight_number'])
        
        #print(m)        
        
        # send empty object if nothing spotted
        if len(m) == 0:
            self.resp_data = { }
            return self.send()

        # construct arrival/departure times for destinations 
        # with more than one flight
        query = """
        SELECT DISTINCT f.flight_number, r.base_airport_iata, 
        r.dest_airport_iata, 
        TIME_FORMAT(f.outbound_length, '%H:%i') as outbound_length, 
        TIME_FORMAT(f.turnaround_length, '%H:%i') as turnaround_length, 
        (aa.timezone - a.timezone) AS delta_tz 
        FROM flights f, routes r, airports a, airports aa 
        WHERE r.route_id = f.route_id 
        AND f.game_id = r.game_id 
        AND f.game_id = '{}' 
        AND f.flight_number in ('{}')
        AND f.deleted = 'N' 
        AND a.iata_code IN ('{}')
        AND a.iata_code = r.base_airport_iata
        AND aa.iata_code = r.dest_airport_iata 
        ORDER BY dest_airport_iata""".format(game_id, "', '".join (sorted(m)), 
                                        "', '".join(sorted(multiples.keys())))
        
        #print(query)
        #print(multiples)
        cursor.execute(query)
        for row in cursor:
            #print(row)
            x = str_to_nptime(multiples[row['base_airport_iata']]
                            [row['dest_airport_iata']]
                            [row['flight_number']]['outbound_dep_time'])
            x = x + str_to_timedelta(row['outbound_length'])
            x = x + timedelta(seconds=int(row['delta_tz'] * 3600))
                
            multiples[row['base_airport_iata']][
                row['dest_airport_iata']][
                row['flight_number']]['inbound_dep_time'] = (
                x + str_to_timedelta(row['turnaround_length'])
                )
        
        
        output = {}
        print(multiples['KWI']['BER'])
        
        # threshold below which flights are considered in conflict
        # for busy routes this can be as low as 30 minutes, but has a default
        # of 60 minutes we diregard gaps >= 120
        minimum_gap = 3600
        #if (threshold is not None and threshold in range(30,120)):
            #minimum_gap = threshold
   
        # process all pairs of flights in multiples to find gaps 
        # of less than 1 hour
        for base in multiples:
            for dest in multiples[base]:
                
                # only compare base/dest pair if not done previously
                pair = sorted([base, dest])
                if pair in self.pairsChecked:
                    continue
                else:
                    self.pairsChecked.append(pair)
                
                
                f = multiples[base][dest]
                #print(dest, f)
                for i in range(0, len(f) - 1):
                    flight_numbers = list(f.keys())
                    for j in range(i+1, len(f)):
                        conflicts = self.getConflicts(f[flight_numbers[i]],
                                                      f[flight_numbers[j]],
                                                      minimum_gap)
                        if len(conflicts) == 0:
                            continue
                        
                        if base not in output:
                            output[base] = dict()
                        if dest not in output[base]: 
                            output[base][dest] = []
                        
                        output[base][dest].append(conflicts)
                        
                
                # now look for flights from dest to base, in case dest is 
                # also one of our bases
                if dest in multiples and base in multiples[dest]:
                    for flight1 in f:
                        for flight2 in multiples[dest][base]:
                            conflicts = self.getConflicts(
                                multiples[base][dest][flight1],
                                multiples[dest][base][flight2],
                                minimum_gap)
                            if len(conflicts) == 0:
                                continue
                            
                            if base not in output:
                                output[base] = dict()
                            if dest not in output[base]: 
                                output[base][dest] = []
                            
                            output[base][dest].append(conflicts)
                    
        
        # sort output by destination
        od = OrderedDict((dest, output[dest]) 
            for dest in sorted(output.keys()))
                
           
        self.resp_data = od
        self.resp.status = 200
  
        return self.send()
        
        
    def put(self):
        # mandatory
        game_id = self.urlvars.get('game_id', None)
        timetable_id = self.urlvars.get('timetable_id', None)

        if (game_id is None or timetable_id is None or 
        not num.match(game_id) or not num.match(timetable_id)):
            # bad request; missing game_id and/or other vars
            return self.error(400, "PUT: Bad game_id or timetable_id")

        return self.create(game_id, timetable_id)
        
    def post(self):
        # mandatory
        game_id = self.urlvars.get('game_id', None)
        timetable_id = self.urlvars.get('timetable_id', None)

        if not num.match(game_id):
            # bad request; missing game_id and/or other vars
            return self.error(400, "POST: Invalid game_id")
            
        return self.create(game_id, timetable_id)
    

    def json_to_db(self, game_id, cursor, data):
        # verify all fields available
        mandatory_fields = ["timetable_name", "fleet_type_id",
            "base_airport_iata", "base_turnaround_delta", "entries"] 

        if not all (k in data for k in mandatory_fields):
            # bad request; missing fields in json
            return False, self.error(400, 
                "Missing fields in json: " + ", ".join(
                list(filter(lambda x: x not in data, mandatory_fields))))

        # not mandatory; set to NULL if not present
        timetable_id = data.get("timetable_id", "NULL")
        if timetable_id is None:
            timetable_id = 'NULL'
        
        if not (timetable_id == 'NULL' or num.match(str(timetable_id))):
            return False, self.error(400, 
                "Invalid timetable_id [{}]".format(timetable_id))
                
        # strip off "entries"
        db_fields = mandatory_fields[:-1]        
        
        # validate time fields
        if not validateTime(data["base_turnaround_delta"]):
            return False, self.error(400, 
                "Invalid base_turnaround_delta [{}]".format(
                data["base_turnaround_delta"]))

        # validate destination airport code
        if not airport.match(data['base_airport_iata']):
            # add field list to error text
            return False, self.error(400, "Bad base_airport_iata [{}]".format(
                data['base_airport_iata']))
    
        # validate all entries
        event_fields = ["flight_number", "dest_airport_iata", "start_time", 
            "start_day", "dest_turnaround_padding", "earliest_available", 
            "post_padding" ]
        time_fields = ["start_time", "dest_turnaround_padding", 
            "earliest_available", "post_padding", ]
        
        # process timetable entries        
        entries = data['entries']

        flight_list = {}
        for e in entries:
            # verify all fields present
            missing = list(filter(lambda x: x not in e, event_fields))
            if len(missing):
                # add field list to error text
                return False, self.error(400, 
                    "{}\nMissing field(s): {}".format(str(e),", ".join(missing)))

            # validate the time fields
            bad_times = list(filter(lambda x: not validateTime(e[x]),
                time_fields))
            if len(bad_times):
                # add field list to error text
                return False, self.error(400, 
                    "{}\r\nBad time field(s): {}".format(str(e),
                    ", ".join(bad_times)))

            # validate destination airport code
            if not airport.match(e['dest_airport_iata']):
                # add field list to error text
                return False, self.error(400, 
                    "{}\nBad destination".format(str(e)))
 
            # validate start day [1..7]
            if not (1 <= int(e['start_day']) <= 7):
                # add field list to error text
                return False, self.error(400, 
                    "{}\nBad start_day".format(str(e)))
            
            if e['flight_number'] != 'MTX':
                flight_list[e['flight_number']] = e['dest_airport_iata']
        
        event_fields.insert(0, 'timetable_id')
        
        # validate supplied flight numbers
        query = """SELECT DISTINCT f.flight_number, r.dest_airport_iata
        FROM flights f, routes r
        WHERE f.game_id = {}
        AND r.route_id = f.route_id
        AND r.game_id = f.game_id
        AND r.base_airport_iata = '{}'
        AND f.fleet_type_id = {}
        AND f.flight_number IN ('{}')
        AND f.deleted = 'N'
        """.format(game_id, data['base_airport_iata'], data['fleet_type_id'],
            "', '".join(flight_list))
        
        cursor.execute(query)
        rows = {}
        for r in cursor:
            rows[r['flight_number']] = r['dest_airport_iata']
            
        # look for missing flights first
        bad_flights = list(filter(
            lambda x: (x not in rows or rows[x] != flight_list[x]), flight_list)
            )
        if len(bad_flights) > 0:
            # add list to error text
            return False, self.error(400, 
                "Unknown flight(s): [{}]".format(", ".join(bad_flights)))
                
        # look for flights already in timetables of this fleet type
        condition = ""
        if timetable_id != 'NULL':
            condition = "AND te.timetable_id <> {}".format(timetable_id)
            
        query = """SELECT t.timetable_id, te.flight_number
        FROM timetables t, timetable_entries te
        WHERE t.game_id = {}
        AND t.timetable_id = te.timetable_id
        AND t.deleted = 'N'
        AND te.flight_number IN ('{}')
        AND t.fleet_type_id = {}
        {}
        """.format(game_id, "', '".join(flight_list), data['fleet_type_id'], 
            condition)

        bad_flights = []
        cursor.execute(query)
        for r in cursor:
            bad_flights.append("({}/{})".format(r['timetable_id'],
                r['flight_number']))
        
        if len(bad_flights):
            return False, self.error(400, 
                "Duplicate flight(s): [{}]".format(", ".join(bad_flights)))
                
        if 'fleet_model_id' not in data:
            data['fleet_model_id'] = ''
        
        insrt = ", ".join(map(lambda x: "'{}'".format(data[x]), db_fields))       
        query = """
        INSERT INTO timetables (game_id, timetable_id, last_modified, 
        timetable_name, fleet_type_id, base_airport_iata, base_turnaround_delta, 
        entries_json) 
        VALUES ({}, {}, NOW(), {}, '{}')
        ON DUPLICATE KEY UPDATE
        timetable_name = values(timetable_name),
        last_modified = values(last_modified),
        entries_json = values(entries_json),
        base_turnaround_delta = values(base_turnaround_delta)
        """.format(game_id, timetable_id, insrt, json.dumps(data['entries']))
        
        cursor.execute(query)
        
        if timetable_id == 'NULL':
            timetable_id = cursor.lastrowid
        
        query = """DELETE FROM 
        timetable_entries WHERE timetable_id = {}""".format(timetable_id)
        cursor.execute(query)
        
        te = []
        for e in entries:
            e['timetable_id'] = timetable_id
            te.append("({})".format(
                ", ".join(map(lambda x: "'{}'".format(e[x]), event_fields))))
        query = """INSERT INTO timetable_entries (timetable_id, flight_number,
        dest_airport_iata, start_time, start_day, dest_turnaround_padding, 
        earliest_available, post_padding) 
        VALUES {}""".format(", ".join(te))

        #print(query)
        cursor.execute(query)
        
        return True, timetable_id

        
    def create(self, game_id, timetable_id):
        """create or update all fields of a timetable"""

        cursor = self.get_cursor()

        if not num.match(game_id):
            # bad request; missing game_id and/or other vars
            return self.error(400, "Invalid game_id")
            
        if timetable_id is not None and not num.match(timetable_id):
            # bad request; missing game_id and/or other vars
            return self.error(400, 
                "Invalid timetable_id [{}]".format(timetable_id))

        # validate the timetable_id
        if timetable_id is not None:
            query = """SELECT * 
            FROM timetables 
            WHERE game_id = {}
            AND timetable_id = {}
            AND deleted = 'N'""".format(game_id, timetable_id)
            
            cursor.execute(query)
            rows = cursor.fetchall()
            if len(rows) < 1:
                return self.error(404, 
                    "No such timetable_id [{}]".format(timetable_id))


        # get json
        data = None
            
        try:
            data = json.loads(self.request.body)
        except ValueError as e:
            pass # return self.error(400, "No valid JSON in body or POST")

        # if there was nothing in the request body, look for form data
        if data is None:
            #print("No valid JSON in body")
            try:
                data = json.loads(str(list(self.request.POST.keys())))
            except ValueError as e:
                pass
                #return self.error(400, "No valid JSON in body or POST")

        #print(json.dumps(data))
        if data is None or (isinstance(data, list) and len(data) == 0):
            return self.error(400, "No valid JSON in body or POST")

        # now we send the data in one element at a time
        if not isinstance(data, list):
            data = [data]
        
        # cannot post multiple objects to single timetable_id
        if len(data) > 1 and timetable_id is not None:
            return self.error(400, 
                              "Cannot POST multiple objects to single id")  

        # put thw whole thing in one transaction
        # either they are all created, or all fail
        #self.db.cnx.autocommit(False)
        
        id_list = []
        href_list = []
        for d in data:
            success, result = self.json_to_db(game_id, cursor, d)
            if not success:
                return result
            else:
                id_list.append(result)
                href_list.append("{}/games/{}/timetables/{}.{}".format(
                    self.request.application_url, game_id, result, 
                    self.content_type))

        # successful creation - commit
        self.db.commit()

        self.resp.status = 200
        self.resp.location = "{}/games/{}/timetables/{}.{}".format(
            self.request.application_url, game_id, 
            ";".join(list(map(str, id_list))), 
            self.content_type)
 
        self.resp_data = { "href" : href_list, "timetable_id" : id_list }
            
        return self.send()
            
TimetableController = rest_controller(Timetables)
