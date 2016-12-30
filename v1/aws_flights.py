from controller import Controller, rest_controller, sortDictList
import simplejson as json
import re
import random
import string
from datetime import datetime
from collections import OrderedDict
from decimal import Decimal
from xml.sax.saxutils import escape
from table_builder import get_html

def getDBDaysFlown(d):
    d = "0" * (7 - len(d)) + d

    out = []
    for x in range(0, 7):
        if (d[x] == '1'):
            out.append(x + 1)
    return out

def validateTime(hhmm):
    fields = hhmm.split(':')
    if len(fields) < 2:
        return False
    return ('00' <= fields[0] < '24' and '00' <= fields[1] < '60')

def validateDelta(hhmm):
    fields = hhmm.split(':')
    if len(fields) < 2:
        return False
    return (re.match(r"^\d+$", fields[0]) and '00' <= fields[1] < '60')

num = re.compile(r"^\d+$")
flNum = re.compile(r"^([A-Z]{2}|[A-Z]\d|\d[A-Z])0*(\d+)$")
iata = re.compile(r"^[A-Z]{3}$")


class Flights(Controller):
    """manages CRUD ops on flights"""

    route_id_map = {}

    def get(self):
        """calls appropriate handler based on self.urlvars"""

        # mandatory
        game_id = self.urlvars.get('game_id', None)

        # for getting arbitrary flights
        flight_number = self.urlvars.get('flight_number', None)
        flight_id = self.urlvars.get('flight_id', None)
        fleet_type_id = self.urlvars.get('fleet_type_id', None)
        if (fleet_type_id is not None):
            fleet_type_id = re.split('[;,]', fleet_type_id)

        # for getting data from a specific base
        base_airport_iata = self.urlvars.get('base_airport_iata', None)

        dest_airport_iata = self.urlvars.get('dest_airport_iata', None)
        if (dest_airport_iata is not None):
            dest_airport_iata = re.split('[;,]', dest_airport_iata)
            
        # remove trailing slashes from PATH_INFO
        path = re.sub(r"\/+$", "", self.request.path)

        # if we get /flight_number/basic, we return only top level data, not
        # a list of full flight details
        basic_only = False
        basic_only = (flight_id is None and re.match(r"basic", path.split("/")[-1:][0]))

        # if flight_number == 'MTX':
            # data = self.getMaintenance()
            # self.resp.text = json.dumps(data).encode('utf-8').decode('unicode_escape')
            # self.resp.cache_control.max_age = int(364.9 * 86400)
            # return self.send()


        #print(self.urlvars, self.request.path, basic_only)

        if not game_id or not num.match(game_id):
            # bad request; missing game_id and/or other vars
            self.resp.status = 400
        elif base_airport_iata is not None:
            return self.__getBaseFlightData(game_id, base_airport_iata,
                fleet_type_id, dest_airport_iata)
        elif (flight_id is not None or flight_number is not None):
            return self.__getFlightData(game_id, flight_id, flight_number,
                basic_only)
        elif game_id is not None:
            return self.__getFlightHeaders(game_id, basic_only)
        else:
            return self.error(400)


    def getFleetTypes(self):
        self.fleet_type_map = {}

        query = "SELECT fleet_type_id, icao_code FROM fleet_types"

        cursor = self.get_cursor()
        cursor.execute(query)

        for row in cursor:
            self.fleet_type_map[row['fleet_type_id']] = row['icao_code']
            
    def getMaintenance(self, game_id):
        # add the special maintenance entry
        mtx_entry = OrderedDict()
        mtx_entry['game_id'] = game_id
        mtx_entry['dest_airport_iata'] = 'MTX'
        mtx_entry['flight_number'] ="MTX"
        mtx_entry['distance_nm'] = 0
        mtx_entry['turnaround_length'] = "05:00"
        mtx_entry['outbound_length'] = "00:00"
        mtx_entry['inbound_length'] = "00:00"
        mtx_entry['delta_tz'] = "0"
        mtx_entry['option_text'] = "Maintenance"
        mtx_entry['class'] ='mtx'
        mtx_entry['empty'] = 'true'
        mtx_entry['fleet_type_id'] = 0
        mtx_entry['dest_city'] = "None"
        mtx_entry['dest_airport_name'] = "None"
        
        return mtx_entry

    def __getBaseFlightData(self, game_id, base_airport_iata, fleet_type_id,
        dest_airport_iata):
        """retrieves flight and fleet type data for all available flights """
        """for a given game_id/base_airport_iata pair"""
        data = OrderedDict([('flights', []), ])

        ft_condition = ""
        if (fleet_type_id is not None):
            ft_condition = "AND f.fleet_type_id IN ({})".format(
                ", ".join(fleet_type_id))
        
        dest_cond = ""
        if (dest_airport_iata is not None):
            dest_cond = "AND r.dest_airport_iata IN ('{}')".format(
                "', '".join(dest_airport_iata))
                
        self.getFleetTypes()

        query = """
            SELECT DISTINCT f.game_id,
            r.base_airport_iata,
            f.flight_number, f.number,
            f.fleet_type_id,
            ft.icao_code AS fleet_type,
            r.dest_airport_iata,
            aa.city AS dest_city,
            aa.airport_name AS dest_airport_name,
            r.distance_nm,
            TIME_FORMAT(f.outbound_length, '%H:%i') AS outbound_length,
            TIME_FORMAT(f.inbound_length, '%H:%i') AS inbound_length,
            TIME_FORMAT(f.turnaround_length, '%H:%i') AS turnaround_length,
            TIME_FORMAT(c.start, '%H:%i') AS curfew_start,
            TIME_FORMAT(c.finish, '%H:%i') AS curfew_finish,
            (aa.timezone - a.timezone) AS delta_tz
            FROM flights f, routes r, airports a, games g, fleet_types ft,
            airports aa LEFT JOIN airport_curfews c
            ON aa.icao_code = c.icao_code
            WHERE f.route_id = r.route_id 
            AND f.game_id = g.game_id 
            AND f.game_id = '{}' 
            AND r.base_airport_iata = '{}' 
            {}
            AND f.turnaround_length is not null 
            AND a.iata_code = r.base_airport_iata 
            AND aa.iata_code = r.dest_airport_iata 
            AND ft.fleet_type_id= f.fleet_type_id
            AND f.deleted = 'N' 
            AND g.deleted = 'N' 
            {}
            ORDER BY dest_city, dest_airport_name, number
            """.format(game_id, base_airport_iata, ft_condition, dest_cond)
        #print(query)

        flight_fields = [
            'game_id', 'flight_number', 'distance_nm', 'fleet_type_id',
            'base_airport_iata', 'dest_airport_iata', 'dest_city',
            'dest_airport_name', 'outbound_length', 'inbound_length',
            'turnaround_length',  'delta_tz',
              ]

        cursor = self.get_cursor()
        cursor.execute(query)
        candidates = {}

        for row in cursor:
            f = OrderedDict((key, row[key]) for key in flight_fields)

            f['game_id'] = row['game_id']
            f['game_id_href'] = "{}/games/{}.{}".format(
               self.request.application_url, row['game_id'], 
               self.content_type)

            f['flight_number_href'] = "{}/games/{}/flights/{}.{}".format(
               self.request.application_url, row['game_id'],
               row['flight_number'], self.content_type)               
            
            f['fleet_type_id'] = row['fleet_type_id']
            f['fleet_type_icao'] = row['fleet_type']
            f['fleet_type_icao_href'] = "{}/fleets/{}.{}".format(
               self.request.application_url, row['fleet_type_id'], 
               self.content_type)

            f['base_airport_iata_href'] = "{}/airports/{}.{}".format(
               self.request.application_url, row['base_airport_iata'], 
               self.content_type)
            f['dest_airport_iata_href'] = "{}/airports/{}.{}".format(
               self.request.application_url, row['dest_airport_iata'], 
               self.content_type)

            
            if row['curfew_start'] is not None:
                f['curfew_start'] = row['curfew_start']
                f['curfew_finish'] = row['curfew_finish']

            data['flights'].append(f)

            # build query condition for sectors
            key = "{}-{}-{}-{}-{}".format(row['game_id'], 
                row['fleet_type_id'], row['base_airport_iata'],
                row['dest_airport_iata'], row['flight_number'])

            if key not in candidates:
                candidates[key] = f
            
        if (len(data['flights'])) == 0:
            return self.error(404)

        # add timetable data        
        timetables = self.getTimetableData(game_id, candidates)
        for flight in data['flights']:
            timetable_id = timetables.get(
                (flight['flight_number'], flight['fleet_type_id']), None
                )
            if timetable_id is not None:
                flight['timetable_id'] = timetable_id
                flight['timetable_id_href'] = ("{}/games/{}/"
                    "timetables/{}.{}").format(self.request.application_url, 
                    game_id, timetable_id, self.content_type)
                    
        # if we got some flights, add MTX at list start
        if dest_airport_iata is None:
            mtx = self.getMaintenance(game_id)
            mtx['base_airport_iata'] = base_airport_iata

            data['flights'].insert(0, mtx)

            
        self.html_template = [{"table_name" : "flights", 
            "entity" : "flight", 
            "fields" : ['game_id', 'flight_number', 
            'fleet_type_icao', 'timetable_id', 'distance_nm', 
            'base_airport_iata', 'dest_airport_iata', 'dest_city',
            'dest_airport_name', 'outbound_length', 'inbound_length',
            'turnaround_length',  'delta_tz'],},]
            
           
        # get the last modification date
        query = """
        SELECT MAX(f.date_added) AS last_modified
        FROM flights f, routes r
        WHERE f.game_id = {}
        AND r.route_id = f.route_id
        AND r.base_airport_iata = '{}'
        AND f.deleted = 'N'
        """.format(game_id, base_airport_iata)
        cursor.execute(query)
        lastm = cursor.fetchone()

        self.resp.last_modified = lastm['last_modified'].timestamp()
        self.resp_data = data
        #print(data)

        return self.send()


    def __getFlightData(self, game_id, flight_id, flight_number, basic):
        """retrieves flight/fleet type data for flight_id or flight number
        For searches by flight number:

        If basic is set, then only one dict is returned per flight, with the
        following fields:
            base_airport_iata
            dest_airport_iata
            distance_nm
            fleet_type_id
            flight_number
            game_id
            inbound_length
            outbound_length
            turnaround_length
            sectors (if valid)
            timetable_id (if valid)

        If basic is not set, one dict is returned for each flight matching the
        flight numbers, and the following fields are also included with the
        previous set:
            flight_id,
            outbound_dep_time,
            outbound_arr_time,
            inbound_dep_time,
            inbound_arr_time,
            days_flown

        Requests using flight_id always returns the complete set of data"""

        self.getFleetTypes()

        output = []
        #basic = False
        self.html_template = [{ "table_name" : "flights", 
            "entity" : "flight", 

            "fields" : [ 'game_id', 'flight_number', 'distance_nm',
            'base_airport_iata', 'dest_airport_iata', 'fleet_type_icao',
            'outbound_length', 'inbound_length', 'turnaround_length', ],
            "optional" : True }]
            
        if not basic:
            self.html_template[0]['fields'].extend(
                ['outbound_dep_time', 'outbound_arr_time', 
                'inbound_dep_time', 'inbound_arr_time', 'days_flown', ])

        self.html_template[0]['fields'].append({ "table_name" : "sectors", 
            "entity" : "flight_sector", "optional" : True,
            "fields" : ["direction", "start_airport_iata", 
            "end_airport_iata", "sector_length", ], })
                
        # we get either flight or flight_number, and bomb if neither is found
        #if (flight_id is None and flight_number is None):
        #    return self.error(400)

        if flight_id is not None:
            fltId = list(set(re.split("[;,]", flight_id)))
            if any(num.match(x) is None for x in fltId):
                return self.error(400)
            condition = "AND (flight_id IN ({}))".format(", ".join(fltId))
        elif (flight_number is not None):
            fltNum = list(set(re.split("[;,]", flight_number)))
            
            # remove MTX from list of flight numbers
            if "MTX" in fltNum:
                fltNum.remove("MTX")
                output.append(self.getMaintenance(game_id))
            
            # run pattern match on all flight numbers
            nums = list(map(lambda x: flNum.search(x), fltNum))
            
            # fail for any invalid flight numbers
            if any(x is None for x in nums):
                err = "Invalid flight nos:" + flight_number
                return self.error(400, err)
                
            digits = [x.group(2) for x in nums]
            condition = "AND (number IN ({}))".format(", ".join(digits))
        else:
            condition = "" # potentially returns a *massive* amount of data


        if not basic:
            qr_frag0 = "f.date_added, f.flight_id,"
            qr_frag1 = """,
            TIME_FORMAT(f.outbound_dep_time, '%H:%i') AS outbound_dep_time,
            TIME_FORMAT(f.outbound_arr_time, '%H:%i') AS outbound_arr_time,
            TIME_FORMAT(f.inbound_dep_time, '%H:%i') AS inbound_dep_time,
            TIME_FORMAT(f.inbound_arr_time, '%H:%i') AS inbound_arr_time,
            BIN(days_flown+0) AS days_flown
            """
            qr_frag2 = ""
        elif flight_id is None:
            qr_frag0 = ""
            qr_frag1 = ""
            qr_frag2 = "GROUP BY flight_number, fleet_type_id"

        query = """
        SELECT DISTINCT f.game_id,
        f.route_id, {} f.number,
        f.flight_number,
        r.base_airport_iata,
        f.fleet_type_id,
        ft.icao_code AS fleet_type,
        r.dest_airport_iata,
        r.distance_nm,
        TIME_FORMAT(f.outbound_length, '%H:%i') AS outbound_length,
        TIME_FORMAT(f.inbound_length, '%H:%i') AS inbound_length,
        TIME_FORMAT(f.turnaround_length, '%H:%i') AS turnaround_length{}
        FROM flights f, routes r, games g, fleet_types ft
        WHERE f.route_id = r.route_id
        AND f.game_id = r.game_id
        AND f.game_id = g.game_id
        AND f.game_id = '{}'
        {}
        AND f.turnaround_length is not null
        AND f.fleet_type_id = ft.fleet_type_id
        AND g.deleted = 'N'
        AND f.deleted = 'N'
        {}
        ORDER BY number
        """.format(qr_frag0, qr_frag1, game_id, condition, qr_frag2)
        #print(query)

        cursor = self.get_cursor()
        cursor.execute(query)

        if cursor.rowcount <= 0:
            return self.error(404)
        #print("Got {} rows".format(cursor.rowcount))

        last_modified = datetime(1970, 1, 1)
        flight_fields = [ 'game_id', 'game_id_href', 'flight_number', 
            'flight_number_href', 'distance_nm', 'base_airport_iata', 
            'base_airport_iata_href', 'dest_airport_iata', 'fleet_type_icao',
            'dest_airport_iata_href', 'fleet_type_icao_href', 'fleet_type_id',
             'outbound_length', 'inbound_length', 'turnaround_length', ]
        
        # add fields for individual flights
        if not basic:
            flight_fields.extend(['flight_id', 'outbound_dep_time', 
                'outbound_arr_time', 'inbound_dep_time', 'inbound_arr_time', 
                'days_flown', ])
            
        flight_fields.extend(['sectors'])

        # check for each flight if it has multiple hops
        possible_sectors = {}

        for row in cursor:
            #print(row)
            # return the href for individual flights if basic is not
            # requested
            if basic:
                identifier = 'flight_number'
            else:
                identifier = 'flight_id'

            if not basic and row['date_added'] > last_modified:
                last_modified = row['date_added']

            row['game_id_href'] = "{}/games/{}.{}".format(
                self.request.application_url, game_id, 
                self.content_type)

            row['flight_number_href'] = "{}/games/{}/flights/{}.{}".format(
                self.request.application_url, game_id, row[identifier], 
                self.content_type)
            
            row['fleet_type_icao'] = row['fleet_type']

            row['fleet_type_icao_href'] = "{}/fleets/{}.{}".format(
                self.request.application_url, row['fleet_type_id'], 
                self.content_type)
            
            for code in ['base_airport_iata', 'dest_airport_iata']:
                row[code + "_href"] = (
                    "{}/airports/{}.{}".format(self.request.application_url,
                    row[code], self.content_type))
            if not basic:
                row['days_flown'] = getDBDaysFlown(row['days_flown'])
            row['sectors'] = []


            f = OrderedDict((key, row[key]) for key in flight_fields)

            output.append(f)

            # build query condition for sectors
            key = "{}-{}-{}-{}".format(row['game_id'], row['route_id'],
                row['fleet_type_id'], row['base_airport_iata'],
                row['dest_airport_iata'])

            if key not in possible_sectors:
                possible_sectors[key] = f
            
        #print(output)

        # required once
        if not basic:
            self.resp.last_modified = last_modified.timestamp()

        actual_sectors = self.getSectorData(possible_sectors)
        timetables = self.getTimetableData(game_id, possible_sectors)
        
        for key in actual_sectors.keys():
            for flight in possible_sectors[key]:
                flight['sectors'] = actual_sectors[key]
        
                
        for flight in output:
            timetable_id = timetables.get(
                (flight['flight_number'], flight['fleet_type_id']), None
                )
            if timetable_id is not None:
                flight['timetable_id'] = timetable_id
                flight['timetable_id_href'] = (
                    "{}/games/{}/timetables/{}.{}".format(
                    self.request.application_url, 
                    game_id, timetable_id, self.content_type)
                )

            
           
        self.resp_data = { "flights" : output }

        return self.send()
        
    def getSectorData(self, possible_sectors):
        actual_sectors = {}

        if len(possible_sectors) == 0:
            return actual_sectors

        sector_qry = []
        for x in possible_sectors.keys():
            a = x.split("-")
            sector_qry.append("""
            (game_id = {} AND route_id = {} AND fleet_type_id = {})
            """.format(a[0], a[1], a[2]))
        
        #print(sector_qry)
        query = """
        SELECT game_id, route_id, fleet_type_id, direction,
        seq_number, start_airport_iata, end_airport_iata,
        TIME_FORMAT(sector_length, '%H:%i') AS sector_length
        FROM route_sectors
        WHERE {}
        ORDER BY direction DESC, seq_number""".format(" OR ".join(sector_qry))
        cursor = self.get_cursor()
        cursor.execute(query)

        for row in cursor:
            key = "{}-{}-{}".format(row['game_id'], row['route_id'],
                row['fleet_type_id'])
            if key not in actual_sectors:
                actual_sectors[key] = []

            for code in ['start_airport_iata', 'end_airport_iata']:
                row[code + "_href"] = (
                    "{}/airports/{}.{}".format(self.request.application_url,
                    row[code], self.content_type))                

            r = OrderedDict([("direction", row["direction"]),
                ("start_airport_iata", row["start_airport_iata"]),
                ("start_airport_iata_href", row["start_airport_iata_href"]),
                ("end_airport_iata", row["end_airport_iata"]),
                ("end_airport_iata_href", row["end_airport_iata_href"]),
                ("sector_length", row["sector_length"])])

            actual_sectors[key].append(r)

        return actual_sectors

    def getTimetableData(self, game_id, candidates):
        """get timetable_id values for all provided flights"""
        timetables = {}

        if len(candidates) == 0:
            return timetables

        tt_qry = []
        for key,val in candidates.items():
            if val["flight_number"] == 'MTX':
                continue
            
            tt_qry.append("(t.base_airport_iata = '{}' "
            "AND t.fleet_type_id = {} "
            "AND te.dest_airport_iata = '{}' "
            "AND te.flight_number = '{}')"
            .format(val["base_airport_iata"], val["fleet_type_id"], 
                    val["dest_airport_iata"], val['flight_number']))

        query = ("SELECT t.timetable_id, t.fleet_type_id, te.flight_number "
        "FROM timetables t, timetable_entries te "
        "WHERE t.game_id = {} "
        "AND t.deleted = 'N' "
        "AND t.timetable_id = te.timetable_id "
        "AND ({}) "
        "ORDER BY flight_number".format(game_id, "\nOR ".join(tt_qry)))
        #print(query)
        cursor = self.get_cursor()
        cursor.execute(query)


        # output is in the followinf format
        # {
        # (flight_number!, fleet_type_id1): timetable_id,
        # (flight_number!, fleet_type_id2): timetable_id, 
        # }
        for row in cursor:
            timetables[(row['flight_number'], row['fleet_type_id'])] = (
                row['timetable_id'])

        return timetables        

    def __getFlightHeaders(self, game_id, basic):
        if basic:
            return self.__getFlightData(game_id, None, None, basic)

        self.html_template = [{"table_name" : "flights", 
            "entity" : "flight", 
            "fields" : ['flight_number']}]
            
        query = """
            SELECT DISTINCT number, flight_number, date_added
            FROM flights f, games g
            WHERE f.game_id = g.game_id
            AND f.deleted = 'N'
            AND g.deleted = 'N'
            AND g.game_id = {}
            ORDER BY number
            """.format(game_id)

        #print(query)
        cursor = self.get_cursor()
        cursor.execute(query)

        last_modified = datetime(1970, 1, 1)
        seen = []
        out = []

        for row in cursor:
            if row['date_added'] > last_modified:
                last_modified = row['date_added']

            if row['flight_number'] not in seen:
                seen.append(row['flight_number'])
                out.append(OrderedDict([
                    ("flight_number", row['flight_number']),
                    ("flight_number_href", "{}/games/{}/flights/{}.{}".format(
                    self.request.application_url, game_id, row['flight_number'], 
                    self.content_type))
                ]))
                
        if len(seen) == 0:
            return self.error(404)

        self.resp_data = { "flights" : out }
        self.resp.last_modified = last_modified.timestamp()

        return self.send()


    def delete(self):
        """permits deletion of a single flight_id or flight_number, or a
        list of either, with comma or semi-colon as separator
        
        /flights/AV001
        /flights/AV001;AV291
        /flights/10229
        /flights/10229;29102
        
        delete flights from a base:
        /flights/LHR    // all from LHR
        /flights/LHR/37 // all fleet type at LHR
        
        """
        cursor = self.get_cursor()

        # mandatory
        game_id = self.urlvars.get('game_id', None)

        # for getting arbitrary flights
        flight_number = self.urlvars.get('flight_number', None)
        flight_id = self.urlvars.get('flight_id', None)
        base_airport_iata = self.urlvars.get('base_airport_iata', None)
        
        if (not game_id or 
        (flight_number is None 
        and flight_id is None 
        and base_airport_iata is None)):
            # bad request; missing game_id and/or other vars
            self.resp.status = 400
            return self.send()
        elif flight_id is not None:
            fltId = list(set(re.split("[;,]", flight_id)))
            #if any(num.match(x) is None for x in fltId):
            #    return self.error(500, err)
            condition = "AND (flight_id IN ({}))".format(", ".join(fltId))
        elif (flight_number is not None):
            fltNum = list(set(re.split("[;,]", flight_number)))

            nums = list(map(lambda x: flNum.search(x), fltNum))
            
            # fail for any invalid flight numbers
            if any(x is None for x in nums):
                err = "Invalid flight nos:" + flight_number
                return self.error(400, err)
                
            digits = [x.group(2) for x in nums]
            condition = "AND (number IN ({}))".format(", ".join(digits))
        elif (base_airport_iata is not None):
            if not re.match(r"^[A-Z]{3}$", base_airport_iata):
                err = "Invalid base airport code:" + base_airport_iata
                return self.error(400, err)               
            condition = "AND base_airport_iata = '{}'".format(base_airport_iata)
        
            fleet_type_id = self.urlvars.get('fleet_type_id', None)
            if fleet_type_id is not None:
                if not re.match(r"^\d+$", fleet_type_id):
                    err = "Invalid fleet_type_id: " + fleet_type_id
                    return self.error(400, err)
                condition += " AND fleet_type_id = {}".format(fleet_type_id)

        query = """
        SELECT flight_id, flight_number, r.base_airport_iata,
        r.dest_airport_iata
        FROM flights f, routes r
        WHERE f.game_id = {}
        AND f.route_id = r.route_id
        AND deleted = 'N'
        {}""".format(game_id, condition)
        cursor.execute(query)

        #print(query)
        if (cursor.rowcount == 0):
            return self.error(404)

        self.resp_data = cursor.fetchall()
        flight_id_list = [str(x['flight_id']) for x in self.resp_data]

        query = """
        UPDATE flights
        SET deleted = 'Y'
        WHERE game_id = {}
        AND deleted = 'N'
        AND flight_id IN ({})""".format(game_id, ", ".join(flight_id_list))
        #print(query)
        cursor.execute(query)

        self.db.commit()
        self.resp.status = 200

        return self.send()

    def put(self):
        """calls appropriate handler based on self.urlvars"""
        # mandatory
        game_id = self.urlvars.get('game_id', None)

        # for getting arbitrary flights
        flight_id = self.urlvars.get('flight_id', None)

        try:
            data = json.loads(self.request.body)
        except ValueError as e:
            return self.error(400, "Invalid json: {}".format(str(e)))

        return self.createFlight(game_id, flight_id, data)


    def createFlight(self, game_id, flight_id, fData):
        """works in two (2) modes:
            * flight_id <> None, data = flight dict array, length 1
            * flight_id == None, data = flight dict array, length > 1
        """
        cursor = self.get_cursor()

        if (not game_id or not isinstance(fData, list) or len(fData) < 1):
            # bad request; missing game_id and/or other vars
            return self.error(400, "Invalid game_id or JSON data")

        if (flight_id is not None
        and (not num.match(flight_id) or len(fData) != 1)):
            return self.error(400, "Invalid flight_id or JSON data")

        # look for attempts to bulldoze an existing flight, where there is an
        # embedded flight_id in the sent payload, which differs from the
        # resource ID
        if (flight_id is not None
        and 'flight_id' in fData[0]
        and fData[0]['flight_id'] != flight_id):
            return self.error(400, "Resource ID [{}] <> JSON flight_id [{}]".
                format(flight_id, fData[0]['flight_id']))

        # check whether there is an instance field
        instance = ''.join(random.choice(string.ascii_lowercase +
                string.ascii_uppercase + string.digits) for _ in range(6))

        all_fields = ["flight_id", "route_id", "number",
        "flight_number", "fleet_type_id", "aircraft_type", "aircraft_reg",
        "outbound_dep_time", "outbound_arr_time", "outbound_length",
        "turnaround_length", "inbound_dep_time", "inbound_arr_time",
        "inbound_length", "deleted",]


        # set defaults for any optional fields
        optional_fields = {"deleted" : "N",  "aircraft_type" : "",
            "aircraft_reg" : "", }

        # if game_name field is in dict, add the game details to DB if needed
        if 'game_name' in fData[0]:
            self.createGame(game_id, fData[0]['game_name'])

        # initialise fleet types
        self.getFleetTypes()

        insrt_rows = []
        out = []
        # validate all dicts; bomb if any are incomplete
        for flight in fData:
            status, error = self.validateFlightData(game_id, flight)
            if not status:
                return self.error(400, error)

            # begin the insert statement
            str = "({}, '{}', NOW(), ".format(game_id, instance)

            # set optional fields to defaults
            for y in filter(lambda x: x not in flight, optional_fields):
                flight[y] = optional_fields[y]

            str += ", ".join(map(lambda x: "'{}'".format(flight[x]),
                all_fields))

            # cannot have enclosing quotes
            str += ", {})".format(flight['days_flown'])

            insrt_rows.append(str)

            # list of hrefs
            out.append("{}/games/{}/flights/{}.{}".format(
                self.request.application_url, game_id, flight['flight_id'], 
                self.content_type))

            # add sector data if provided
            if 'sectors' in flight:
                res, err = self.createRouteSectors(game_id, flight['route_id'],
                    flight['fleet_type_id'], flight['sectors'])

                if not res:
                    return self.error(500, err)

        query = """
        INSERT INTO flights (game_id, instance, date_added, flight_id,
        route_id, number, flight_number, fleet_type_id, aircraft_type,
        aircraft_reg, outbound_dep_time, outbound_arr_time, outbound_length,
        turnaround_length, inbound_dep_time, inbound_arr_time,
        inbound_length, deleted, days_flown)
        VALUES
        {}
        ON DUPLICATE KEY UPDATE
        instance = values(instance),
        date_added = values(date_added),
        flight_number = values(flight_number),
        number = values(number),
        fleet_type_id = values(fleet_type_id),
        aircraft_type = values(aircraft_type),
        aircraft_reg = values(aircraft_reg),
        outbound_dep_time = values(outbound_dep_time),
        outbound_arr_time = values(outbound_arr_time),
        outbound_length = values(outbound_length),
        turnaround_length = values(turnaround_length),
        inbound_dep_time = values(inbound_dep_time),
        inbound_arr_time = values(inbound_arr_time),
        inbound_length = values(inbound_length),
        days_flown = values(days_flown),
        deleted = values(deleted)""".format(", ".join(insrt_rows));
        cursor.execute(query)

        self.db.commit()
        self.resp.status = 201

        self.resp_data = out

        return self.send()


    def validateFlightData(self, game_id, data):
        """runs through flightData and returns (true, None) if all
        fields are good, or (False, error_text) on failure"""

        # validate presence of all required fields
        mandatory_fields = ["fleet_type_id", "flight_number",
            "outbound_dep_time", "outbound_arr_time", "outbound_length",
            "turnaround_length", "inbound_dep_time", "inbound_arr_time",
            "inbound_length", "days_flown", "base_airport_iata",
            "dest_airport_iata"]

        time_fields = ["outbound_dep_time", "outbound_arr_time",
             "inbound_dep_time", "inbound_arr_time", "inbound_arr_time", ]

        delta_fields = [ "outbound_length", "turnaround_length",
            "inbound_length" ]

        all_fields = ["flight_id", "route_id",
        "flight_number", "fleet_type_id", "aircraft_type", "aircraft_reg",
        "outbound_dep_time", "outbound_arr_time", "outbound_length",
        "turnaround_length", "inbound_dep_time", "inbound_arr_time",
        "inbound_length", "deleted",]

        if not all (k in data for k in mandatory_fields):
            # bad request; missing fields in json
            error_text = "Missing fields in json: " + ", ".join(
                list(filter(lambda x: x not in data, mandatory_fields)))
            return (False, error_text)

        # validae flight number
        # flight_number must be of one of the two forms:
        # IATA XX0*<num> e.g. AA99, AA099, AA0099
        # or ICAO XXX0*<num> e.g. AAL99, AAL099, AAL0099
        m = flNum.search(data['flight_number'])
        if m is None:
            err = "Invalid flight_number [{}]".format(data['flight_number'])
            return (False, err)

        # validate or set number field
        if 'number' in data:
            if int(data['number']) <= 0:
                return (False, "Bad 'number' [{}]".format(data['number']))

            if int(m.group(2)) != int(data['number']):
                return (False,
                    "Mismatch 'number' and 'flight_number: [{}/{}]".format(
                    data['number'], data['flight_number']))
        else:
            data['number'] = m.group(2)
            #print("Setting number = {}".format(m.group(2)))


        # validate time fields
        tf = { key:value for key,value in data.items() if key in time_fields }
        failed = list(filter(lambda x: not validateTime(data[x]), tf.keys()))
        if len(failed):
            # add field list to error text
            error_text = "Invalid time value(s): {}".format(", ".join(failed))
            return (False, error_text)

        # validate duration fields
        tf = { key:value for key,value in data.items() if key in delta_fields }
        failed = list(filter(lambda x: not validateDelta(data[x]), tf.keys()))
        if len(failed):
            # add field list to error text
            error_text = "Invalid time delta(s): {}".format(", ".join(failed))
            return (False, error_text)

        # validate days_flown
        days = self.getDaysFlown(data['days_flown'])
        if days is None:
            error_text = "Invalid days_flown: [{}]".format(data['days_flown'])
            return (False, error_text)
        else:
            data['days_flown'] = days

        # validate fleet type; if the fleet type is not in the DB, look for
        # useful fields (turnaround lengths, ICAO code, etc) in the data; if
        # they are available, add them to the DB; otherwise fail
        if int(data['fleet_type_id']) not in self.fleet_type_map.keys():
            #print("Unknown fleet_type_id [{}]".format(data['fleet_type_id']))
            if all(x in data for x in ['fleet_type', 'min_turnaround']):
                self.addFleetType(game_id, data['fleet_type_id'],
                    data['fleet_type'], data['min_turnaround'])
            else:
                return (False,
                    "Unknown fleet_type_id [{}]".format(data['fleet_type_id']))

        # validate sector data if provided
        if 'sectors' in data:
            res, err = self.validateRouteSectors(data['base_airport_iata'],
                data['dest_airport_iata'], data['sectors'])
            if not res:
                return (False, err)

        # validate supplied route_id, or attempt to create one from base/dest
        (route_id, err) = self.validateRouteId(game_id, data.get('route_id', ''),
            data.get('base_airport_iata', ''),
            data.get('dest_airport_iata', ''),
            data.get('distance_nm', None), data['fleet_type_id'])
        if not route_id:
            return (False, err)
        else:
            data['route_id'] = route_id

        return (True, None)

    def getFleetTypes(self):
        self.fleet_type_map = {}

        query = "SELECT * FROM fleet_types"

        cursor = self.get_cursor()
        cursor.execute(query)

        for row in cursor:
            self.fleet_type_map[row['fleet_type_id']] = row

    def addFleetType(self, fleet_type_id, fleet_type, min_turnaround):
        pass

    def validateRouteSectors(self, base_airport_iata, dest_airport_iata, data):
        """check all entries of any supplied route_sectors"""
        if len(data) == 0:
            return (False, "Empty sector list provided")

        # fail if any of the mandatory fields are missing
        mandatory_fields = ["start_airport_iata", "distance_nm", "sector_length",
            "end_airport_iata", "direction", "seq_number"]

        entries = { "out" : [], "in" : [] }

        for sector in data:
            # fail for missing fields
            if not all (k in sector for k in mandatory_fields):
                return (False, "Missing sector fields: {}".format(
                    list(filter(lambda x: x not in sector, mandatory_fields))))

            # fail for invalid direction
            if sector["direction"] in [ "out", "in" ]:
                entries[sector["direction"]].append(sector)
            else:
                return (False, "Invalid direction value: {}".format(sector))

        pairs = { "out" : (base_airport_iata, dest_airport_iata),
            "in" : (dest_airport_iata, base_airport_iata) }

        for direction in [ "out", "in" ]:
            # sort by seq_number
            entries[direction] = sortDictList("seq_number", entries[direction])

            # verify seq_number is 0 .. len-1
            seq_numbers = list(set(map(lambda x: x["seq_number"],
                entries[direction])))
            if seq_numbers != list(range(0, len(entries[direction]))):
                return (False, "Bad route sequence numbers")

            # get first start and last end airports;
            # fail if if they do not match base/destination
            first, last = (entries[direction][0]["start_airport_iata"],
              entries[direction][len(entries[direction])-1]["end_airport_iata"])

            if (first, last) != pairs[direction]:
                return (False, "{}bound: bad start/end airports: {}".format(
                    direction, (first, last)))

            # validate time field
            for s in entries[direction]:
                if not validateTime(s["sector_length"]):
                    return (False,
                        "Bad sector length {}".format(s["sector_length"]))

        return (True, "")


    def createRouteSectors(self, game_id, route_id, fleet_type_id, data):
        """add entries to the route_sectors table"""

        if len(data) == 0:
            return (False, "Empty sector list provided")

        cursor = self.get_cursor()

        # first we delete any existing entries; for a given combination of
        # flight number, route_id and fleet_type_id, there can be only one
        # set of rows.
        query = """
        DELETE FROM route_sectors
        WHERE game_id = {}
        AND route_id = {}
        AND fleet_type_id = {}
        """.format(game_id, route_id, fleet_type_id)
        cursor.execute(query)

        # build insert qry
        qry = []

        for sector in data:
             qry.append("({}, {}, {}, '{}', {}, '{}', '{}', '{}')".format(
                game_id, route_id, fleet_type_id,
                sector['direction'], sector['seq_number'],
                sector['start_airport_iata'], sector['end_airport_iata'],
                sector['sector_length']))

        query = """
        INSERT INTO route_sectors
        (game_id, route_id, fleet_type_id, direction, seq_number,
        start_airport_iata, end_airport_iata, sector_length)
        VALUES {}""".format(", ".join(qry))
        cursor.execute(query)
        self.db.commit()

        if cursor.rowcount > 0:
            return (True, "")
        else:
            return (False, "Unable to insert rows")

    def post(self):
        """
        it is possible to POST to either the /flights/ collection, or to a
        specific flight_id or flight_number.

        /flights/: Posting to the collection is the equivalent of a PUT,
        requiring all fields to be present

        /flights/<flight_id>: POSTing to a single flight_id allows a subset of
        fields to be modified for that flight only

        /flights/<flight_number>: POSTing to a flight_number is more risky, but
        allows a subset of fields to be modified for all flights with that
        number, provided certain conditions are met
        """
        post_fields = ['flight_number', 'number', 'fleet_type_id', 
            'aircraft_type', 'aircraft_reg', 'outbound_dep_time', 
            'outbound_arr_time', 'outbound_length', 'turnaround_length', 
            'inbound_dep_time', 'inbound_arr_time', 'inbound_length', 
            'deleted', ]

        cursor = self.get_cursor()

        # mandatory
        game_id = self.urlvars.get('game_id', None)

        if not game_id or not num.match(game_id):
            # bad request; missing game_id
            return self.error(400, "Invalid or missing game_id")

        # for getting arbitrary flights
        flight_id = self.urlvars.get('flight_id', None)
        flight_number = self.urlvars.get('flight_number', None)

        # reject attempts to post to multiple flight_id or flight_numbers,
        # unless the specified flight_number refers to multiple flights
        if ((flight_id is not None and flight_id.find(";") != -1)
        or (flight_number is not None and flight_number.find(";") != -1)):
            return self.error(400, "Cannot POST to multiple flights")

        # get json
        data = None

        try:
            data = json.loads(self.request.body)
        except ValueError as e:
            #print("No valid JSON in body")
            pass # return self.error(400, "No valid JSON in body or POST")

        # if there was nothing in the request body, look for form data
        if data is None:
            try:
                data = json.loads(str(list(self.request.POST.keys())))
            except ValueError as e:
                return self.error(400, "No valid JSON in body or POST")
        #print(self.request.POST)
        #print(data)


        if not (isinstance(data, dict) or isinstance(data, list)):
            return self.error(400, "No valid data provided")

        # a list of flight dictionaries is received, we create new flights if
        # we have been sent here from a collection level resource,
        # i.e. POST /flights
        # for any other condition, we carp
        if isinstance(data, list):
            if flight_id is None and flight_number is None:
                return self.createFlight(game_id, flight_id, data)
            else:
                # bad request; cannot POST multiple flights to single resource
                return self.error(400, "Multiple flights sent to single ID")

        # reject JSON payloads containing no expected fields
        if all(x not in post_fields for x in data.keys()):
            # bad request: all expected fields missing
            return self.error(400, "No flight data fields provided")

        # if neither flight_id nor flight_number are provided, then we do
        # a full create using the JSON payload; thus we must ensure we have a
        # flight_id from somewhere
        # POST /flights/
        if flight_id is None and flight_number is None:
            if 'flight_id' not in data or not num.match(data['flight_id']):
                # bad request; missing flight_id
                return self.error(400, "Invalid or missing flight_id")
            flight_id = data['flight_id']

            return self.createFlight(game_id, flight_id, [data])

        # we now validate the supplied flight_id or flight_number; if it exists
        # then we do an update, otherwise we do a full create
        # choose one or the other
        if flight_id is not None:
            condition = "flight_id = '{}'".format(flight_id)
            identifier = flight_id
            identifier_type = 'flight_id'
        else:
            condition = "flight_number = '{}'".format(flight_number)
            identifier = flight_number
            identifier_type = 'flight_number'



        # look for attempts to bulldoze an existing flight, where there is an
        # embedded flight_id in the sent payload, which differs from the
        # resource ID
        if (identifier_type == 'flight_id'
        and 'flight_id' in data and int(data['flight_id']) != int(flight_id)):
            return self.error(400,
                "POST: Resource ID [{}] <> JSON flight_id [{}]".
                format(int(flight_id), int(data['flight_id'])))


        # look for flights matching the flight_id or flight_number
        query = """SELECT flight_id, flight_number
        FROM flights
        WHERE game_id = {}
        AND deleted = 'N'
        AND {}""".format(game_id, condition)
        cursor.execute(query)

        rows = cursor.fetchall()

        # if nothing matches these details, create a new flight
        if len(rows) == 0:
            flight_id = data.get('flight_id', None)
            return self.createFlight(game_id, flight_id, [data])
          
        # validate flight numbers if a flight number change is in JSON
        if not self.validateFlightNumbers(game_id, flight_number, flight_id, data):
            # bad request; changes flight numbers invalid
            return self.error(400, "Invalid change to flight number")

        time_fields = ["outbound_dep_time", "outbound_arr_time",
             "inbound_dep_time", "inbound_arr_time", "inbound_arr_time", ]

        delta_fields = [ "outbound_length", "turnaround_length",
            "inbound_length" ]

        # validate time fields
        tf = { key:value for key,value in data.items() if key in time_fields }
        failed = list(filter(lambda x: not validateTime(data[x]), tf.keys()))
        if len(failed):
            # add field list to error text
            return self.error(400,
                "Invalid time value(s): {}".format(", ".join(failed)))

        # validate duration fields
        tf = { key:value for key,value in data.items() if key in delta_fields }
        failed = list(filter(lambda x: not validateDelta(data[x]), tf.keys()))
        if len(failed):
            # add field list to error text
            error_text = "Invalid time delta(s): {}".format(", ".join(failed))
            return (False, error_text)

        # check whether there is an instance field
        if 'instance' not in data:
            data['instance'] = ''.join(random.choice(string.ascii_lowercase +
                string.ascii_uppercase + string.digits) for _ in range(6))

        update_qry = "date_added = NOW(), instance = '{}'".format(data['instance'])

        # validate days_flown
        if 'days_flown' in data:
            days = self.getDaysFlown(data['days_flown'])
            if days is None:
                return self.error(400,
                    "Invalid days_flown: [{}]".format(data['days_flown']))
            else:
                # days_flown is the only field which cannot be
                #enclosed in quotes
                update_qry += ", days_flown = {}".format(days)


        new_fields = ", ".join(map(lambda y: "{} = '{}'".format(y, data[y]),
            filter(lambda x: x in post_fields, data.keys())))

        if new_fields != '':
            update_qry = update_qry + ", " + new_fields

        query = """UPDATE flights SET {}
        WHERE game_id = {}
        AND {}
        AND deleted = 'N'""".format(update_qry, game_id, condition)

        #print(query)
        cursor.execute(query)
        self.db.commit()
        if (cursor.rowcount <= 0):
            return self.error(404)
            
        # on flight number change, update timetable_entries with new number
        #
        # get any flight_number difference
        if ("flight_number" in data 
        and rows[0]["flight_number"] != data["flight_number"]):
            # first we change the location URI
            if identifier_type == 'flight_number':
                identifier = data["flight_number"]
                
            query = """UPDATE timetable_entries te, timetables t
            SET te.flight_number = '{}'
            WHERE te.flight_number = '{}'
            AND t.game_id = {}
            AND t.timetable_id = te.timetable_id
            AND t.deleted = 'N'""".format(data["flight_number"], 
                rows[0]["flight_number"], game_id)
            #print(query)
            cursor.execute(query)
            self.db.commit()


        self.resp.status = 200
        self.resp.location = "{}/games/{}/flights/{}.{}".format(
            self.request.application_url, game_id, identifier, 
            self.content_type)
        out = { "href" : self.resp.location }
        
        self.resp_data = out

        return self.send()

    def createGame(self, game_id, game_name):
        if game_id is None or not num.match(game_id):
            return

        # look in the database for this game_id
        query = """SELECT *
        FROM games
        WHERE game_id = {}
        AND deleted = 'N'""".format(game_id)

        cursor = self.get_cursor()
        cursor.execute(query)

        x = cursor.fetchall()
        if len(x) > 0:
            return

        query = """INSERT INTO games (game_id, name)
        VALUES ('{}', "{}")""".format(game_id, game_name)

        cursor.execute(query)
        self.db.commit()



    def validateRouteId(self, game_id, route_id, base_airport_iata,
        dest_airport_iata, distance_nm, fleet_type_id):
        """
        if no route_id is provided, search using game_id, base_airport_iata
        and dest_airport_iata, or create and return a new one if required;

        if a route_id is provided, verify that it matches the game_id supplied

        return a valid route_id, or None on failure
        """
        # validate base_airport_iata and dest_airport_iata
        if not(iata.match(base_airport_iata) and iata.match(dest_airport_iata)):
            return (None,
                "Bad route: bad base/dest {}/{}".format(base_airport_iata,
                dest_airport_iata))

        # reject base and destination as the same airport
        if base_airport_iata == dest_airport_iata:
            return (None,
                "Bad route: same base/dest {}/{}".format(base_airport_iata,
                dest_airport_iata))

        if distance_nm is None or not (isinstance(distance_nm, int) or
            num.match(distance_nm)):
            return (None,
                "Bad route: bad distance_nm {}".format(distance_nm))

        # check whether we've seen it before
        key = "{}-{}-{}-{}".format(game_id, base_airport_iata,
            dest_airport_iata, distance_nm)

        if key in Flights.route_id_map:
            return (Flights.route_id_map[key], None)

        cursor = self.get_cursor()

        if(not fleet_type_id or not num.match(fleet_type_id)):
            return (None,
                "Unknown fleet_type_id [{}]".format(fleet_type_id))


        # validate route_id if provided
        if num.match(route_id):
            query = """
            SELECT *
            FROM routes r, airports a, airports aa
            WHERE r.game_id = {}
            AND r.route_id = {}
            AND r.base_airport_iata = '{}'
            AND r.dest_airport_iata = '{}'
            AND a.iata_code = r.base_airport_iata
            AND aa.iata_code = r.dest_airport_iata
            AND distance_nm = {}""".format(game_id, route_id, base_airport_iata,
                dest_airport_iata, distance_nm)

            cursor.execute(query)
            data = cursor.fetchall()
            if (len(data)):
                Flights.route_id_map[key] = route_id
                return (route_id, None)
            else:
                return (None,
                    "validateRouteId(): Invalid route_id {}".format(route_id))


        # look for a simple route with this base/destination
        query = """
        SELECT r.route_id, direction, seq_number, start_airport_iata,
        end_airport_iata
        FROM (routes r LEFT JOIN route_sectors rs
        ON r.game_id = rs.game_id
        AND r.route_id = rs.route_id
        AND rs.fleet_type_id = {}), airports a, airports aa
        WHERE r.game_id = {}
        AND a.iata_code = r.base_airport_iata
        AND aa.iata_code = r.dest_airport_iata
        AND base_airport_iata = '{}'
        AND dest_airport_iata = '{}'
        AND distance_nm = {}
        ORDER BY direction, seq_number
        """.format(fleet_type_id, game_id, base_airport_iata, dest_airport_iata,
            distance_nm)

        cursor.execute(query)
        data = cursor.fetchall()
        if (len(data)) > 0:
            Flights.route_id_map[key] = data[0]['route_id']
            return (data[0]['route_id'], None)

        # create a new one and return its route_id
        query = """
        INSERT INTO routes
        (game_id, base_airport_iata, dest_airport_iata, distance_nm)
        VALUES ({}, '{}', '{}', {})""".format(game_id, base_airport_iata,
            dest_airport_iata, distance_nm)

        cursor.execute(query)
        self.db.commit()

        Flights.route_id_map[key] = cursor.lastrowid

        return (cursor.lastrowid, None)


    def validateFlightNumbers(self, game_id, old_flight_number, flight_id, data):
        """if changing flight number in a POST, ensure new flight number is not
        already in use on a different route

        this does not protect us from having the same flight number twice on the
        same day!!!"""
        # pass if no flight_number supplied
        new_flight_number = data.get('flight_number', None)
        if new_flight_number is None:
            return (True, "")

        # flight_number must be of one of the two forms:
        # IATA XX0*<num> e.g. AA99, AA099, AA0099
        # or ICAO XXX0*<num> e.g. AAL99, AAL099, AAL0099
        m = flNum.search(new_flight_number)
        if m is None or m.group(2) == 0:
            return (False, 
                "Invalid flight_number: {}".format(new_flight_number))
        digits = [m.group(2)]
        
        # if the URI flight_number and the new value are the same, pass
        if old_flight_number is not None:
            # do a full flight number comparison
            if old_flight_number == new_flight_number:
                return (True, "")
            
            # get the digits out
            q = flNum.search(old_flight_number)
            
            # success if numeric part of flight numbers match
            if int(m.group(2)) == int(q.group(2)):
                return (True, "")
            digits.append(q.group(2))
            
        # validate or set number field
        if 'number' in data:
            if int(data['number']) <= 0:
                return (False, "Bad number field: {}".format(data['number']))

            # number field does not match flight_number
            if int(m.group(2)) != int(data['number']):
                return (False, 
                    "Mismatch flight_number/number: {}".format(data))
        else:
            data['number'] = m.group(2)

        cursor = self.get_cursor()
            
        # validate against all other numbers
        query = """SELECT DISTINCT number
        FROM flights
        WHERE game_id = {}
        AND number <> {}
        AND deleted = 'N'""".format(game_id, data['number'])
        cursor.execute(query)
        
        # it must not match 
        all_numbers = [r['number'] for r in cursor]
        if any(data['number'] in [x, x+1] for x in all_numbers):
            return (False, "flight_number already in use: {}".format(
                new_flight_number))
        

        flt_num_condition = "number IN ('{}')".format("', '".join(digits))

        flt_id_condition = ""
        if flight_id is not None:
            flt_id_condition = "OR flight_id = {}".format(flight_id)


        # get the route_ids for the new and old flight numbers and flight_id
        query = """SELECT DISTINCT flight_number, route_id
        FROM flights
        WHERE game_id = {}
        AND ({} {})
        AND deleted = 'N'""".format(game_id, flt_num_condition, flt_id_condition)
        #print(query)
        cursor.execute(query)

        # if we see any change in route_id, fail
        route_id = 0
        for r in cursor:
            if route_id == 0:
                route_id = r['route_id']
                continue
            else:
                if r['route_id'] != route_id:
                    return (False, "Invalid change to new route")

        # all flights are the same route
        return (True, "")


    def getDaysFlown(self, days_flown):
        if re.match(r"^b'[01]{7}'$", days_flown):
            return days_flown
        elif re.match("^[1\-][2\-][3\-][4\-][5\-][6\-][7\-]$", days_flown):
            x = re.sub(r"\d", "1", days_flown)
            return "b'" +re.sub(r"\D", "0", x)+"'"
        elif isinstance(days_flown, list):
            # fail if any value is not in [1..7]
            if not all(1 <= x <= 7 for x in days_flown):
                return None
            # fail if we have repeated entries, e.g. [1, 2, 3, 3]
            elif len(set(days_flown)) != len(days_flown):
                return None
            else:
                x = re.sub(r"\d", "1", "".join(sorted(days_flown)))
                return "b'" +re.sub(r"\D", "0", x)+"'"

FlightController = rest_controller(Flights)
