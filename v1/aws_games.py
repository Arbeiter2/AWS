from controller import Controller, rest_controller
import simplejson as json
import re
from datetime import datetime
from collections import OrderedDict

class Games(Controller):
    def get(self):
        #print(self.urlvars)
        bases = self.urlvars.get('bases', None)
        mode = self.urlvars.get('mode', None)
        game_id = self.urlvars.get('game_id', None)

        if bases:
            if bases == 'bases':
                return self.getGameAirportData(game_id, 'base')
            else:
                return self.error(404)

        if game_id:
            if mode == 'fleets':
                return self.getFleetTypes(game_id)
            elif mode == 'bases':
                return self.getGameAirportData(game_id, 'base')
            elif mode == 'airports':
                return self.getGameAirportData(game_id, 'dest')
            else:
                return self.getGameSummary(game_id)
           
        return self.getGameHeaders()

    def getGameHeaders(self):
        cursor = self.get_cursor()

        query = """
            SELECT game_id, name 
            FROM games
            WHERE deleted = 'N'
            ORDER BY name"""
        cursor.execute(query)
        rows = cursor.fetchall()
        
        for r in rows:
            r['game_id_href'] = "{}/games/{}.{}".format(
                self.request.application_url, r['game_id'], self.content_type)

        self.html_template = [{"table_name" : "games", "entity" : "game",
            "fields" : ["game_id", "name", ]}]
            
        #self.resp.text = json.dumps(rows)
        self.resp_data = { "games" : rows }
        
        return self.send()

    def getGameSummary(self, game_id):
        if game_id is None or not re.match(r"^\d+([;,]\d+)*$", game_id):
            return self.error(400)
            
        res = []
        game_id_list = "', '".join(re.split(r"[;,]", game_id))

        query = """
        SELECT g.game_id, g.name as game_name, a.name as airline_name, 
        base_airport_iata, a.iata_code, a.icao_code
        FROM games g LEFT JOIN 
        (SELECT * FROM airlines WHERE game_id IN ('206') AND deleted = 'N') a 
        ON g.game_id = a.game_id
        WHERE g.game_id IN ('206') 
        AND g.deleted = 'N'
        """.format(game_id_list, game_id_list)
        print(query)
        cursor = self.get_cursor()
        cursor.execute(query)
        if cursor.rowcount <= 0:
            return self.error(404)
            
        # base data
        for row in cursor:
            out = OrderedDict()
            out['game_id'] = row['game_id']
            out['game_name'] = row['game_name']
            out['airline_name'] = row['airline_name']
            out['base_airport_iata'] = row['base_airport_iata']
            out['iata_code'] = row['iata_code']
            out['icao_code'] = row['icao_code']
            
            out['bases'] = "{}/games/{}/bases.{}".format(
                self.request.application_url, row['game_id'], 
                self.content_type)
            out['bases_href'] = out['bases']

            # flight data
            out['flights'] = "{}/games/{}/flights.{}".format(
                    self.request.application_url, row['game_id'], 
                    self.content_type)
            out['flights_href'] = out['flights']
            
            # timetable data
            out['timetables'] = "{}/games/{}/timetables.{}".format(
                    self.request.application_url, row['game_id'], 
                    self.content_type)
                    
            out['timetables_href'] = out['timetables']        

            res.append(out)

        self.html_template = [{"table_name" : "games", 
        "entity" : "game",
            "fields" : ["game_id", "game_name", "airline_name", 
                        "base_airport_iata",
                        "iata_code", "icao_code", "bases", "flights", 
                        "timetables"],
            "stacked_headers" : True}]

        self.resp_data = { "games" : res }
        #print(out)
        #self.resp.text = json.dumps(out)
       
        return self.send()
        
       
    def getGameAirportData(self, game_id, mode):
        if mode == 'base':
            label = 'bases'
        elif mode == 'dest':
            label = 'destinations'
        else:
            return self.error(400)
            
        condition = ""
        if game_id is not None:
            if not re.match(r"^\d+$", game_id):
                return self.error(400)
            else:
                condition = "AND g.game_id = {}".format(game_id)
        
        cursor = self.get_cursor()
        
        games = {}
        seen = []
        base_fields = [ 'iata_code', 'iata_code_href', 'icao_code', 
            'icao_code_href', 'city', 'airport_name',  'timezone' ]

        query = '''
SELECT DISTINCT qw.game_id, qw.name, qw.iata_code,
a.icao_code, a.timezone, a.city, a.airport_name,
TIME_FORMAT(c.start, '%H:%i') AS curfew_start,
TIME_FORMAT(c.finish, '%H:%i') AS curfew_finish
FROM airports a LEFT JOIN airport_curfews c
ON a.icao_code = c.icao_code,
(SELECT DISTINCT g.game_id, g.name, r.{}_airport_iata as iata_code
FROM games g, routes r, flights f
WHERE g.deleted = 'N'
AND f.deleted = 'N'
AND r.game_id = f.game_id
AND r.route_id = f.route_id
AND r.game_id = g.game_id
UNION 
SELECT DISTINCT al.game_id, g.name, al.base_airport_iata as iata_code
FROM games g, airlines al
WHERE g.deleted = 'N'
AND g.game_id = al.game_id) qw
WHERE qw.iata_code = a.iata_code
{}
ORDER BY name, city
        '''.format(mode, condition)
        #print(query)
        cursor.execute(query)
        rows = cursor.fetchall()

        last_modified = datetime(1970, 1, 1)
        for r in rows:
            if r['game_id'] not in games:
                games[r['game_id']] = OrderedDict()
                games[r['game_id']]['game_id'] = r['game_id']
                games[r['game_id']]["name"] = r['name']
                games[r['game_id']]['game_id_href'] = "{}/games/{}.{}".format(
                    self.request.application_url, r['game_id'], self.content_type)
                games[r['game_id']][label] = []
            
            r['iata_code_href'] = "{}/airports/{}.{}".format(
                    self.request.application_url, r['iata_code'], self.content_type)
            r['icao_code_href'] = "{}/airports/{}.{}".format(
                    self.request.application_url, r['icao_code'], self.content_type)
            
            airport = OrderedDict((key, r[key]) for key in base_fields)
            if r['curfew_start'] is not None:
                airport['curfew_start'] = r['curfew_start']
                airport['curfew_finish'] = r['curfew_finish']
                
            #if r['date_added'] is not None and r['date_added'] > last_modified:
            #    last_modified = r['date_added']
            #del r['date_added']
                
            games[r['game_id']][label].append(airport)
            seen.append(r['iata_code'])
            

        # add tech stops for destination airport request
        if mode == 'dest':
            query = """
            SELECT DISTINCT rs.game_id, start_airport_iata as iata_code, 
            a.icao_code, a.timezone, a.city, a.airport_name,
            TIME_FORMAT(c.start, '%H:%i') AS curfew_start,
            TIME_FORMAT(c.finish, '%H:%i') AS curfew_finish
            FROM route_sectors rs, routes r, flights f, 
            airports a LEFT JOIN airport_curfews c
            ON a.iata_code = c.iata_code
            WHERE rs.game_id IN ({})
            AND rs.game_id = r.game_id
            AND r.game_id = f.game_id
            AND rs.route_id = r.route_id
            AND r.route_id = f.route_id
            AND f.deleted = 'N'
            AND a.iata_code = start_airport_iata
            """.format(", ".join(map(lambda x: str(x), games.keys())))
            
            cursor.execute(query)
            for r in cursor:
                r['iata_code_href'] = "{}/airports/{}.{}".format(
                    self.request.application_url, r['iata_code'],
                    self.content_type)
                r['icao_code_href'] = "{}/airports/{}.{}".format(
                    self.request.application_url, r['icao_code'], 
                    self.content_type)

                if r['iata_code'] not in seen:
                    airport = OrderedDict(
                        (key, r[key]) for key in base_fields 
                    )
                    if r['curfew_start'] is not None:
                        airport['curfew_start'] = r['curfew_start']
                        airport['curfew_finish'] = r['curfew_finish']
                    #print(airport)
                        
                    games[r['game_id']][label].append(airport)
        #print(games)
 
        #out = sortDictList("name", games.values())
        out = sorted(games.values(), key=lambda x: x['name'])
                   
        #self.resp.text = json.dumps(out, encoding="ISO-8859-1")
        self.html_template = [{ "table_name" : "airports",
            "entity" : "game",
            "fields" : ["game_id", "name", 
            {"table_name" : label, "entity" : "airport",
            "fields" : [ 'iata_code', 'icao_code', 'city', 'airport_name', 
            'timezone', 'curfew_start', 'curfew_finish']}],
            "stacked_headers" : True }]
            
        self.resp_data = { "airports" : out }
        #print(last_modified)
        #self.resp.last_modified = last_modified.timestamp()
            
        return self.send()

    def getFleetTypes(self, game_id):
        condition = ""
        if game_id is not None:
            if not re.match(r"^\d+$", game_id):
                return self.error(400)
            else:
                condition = "AND g.game_id = {}".format(game_id)
            
        cursor = self.get_cursor()

        last_modified = datetime(1970, 1, 1)
        query = """
            SELECT DISTINCT f.game_id, base_airport_iata, f.fleet_type_id, 
            description, icao_code,
            TIME_FORMAT(ft.turnaround_length, '%H:%i') AS min_turnaround,
            TIME_FORMAT(ft.ops_turnaround_length, '%H:%i') AS ops_turnaround
            FROM fleet_types ft, flights f, games g, routes r
            WHERE f.game_id = g.game_id
            AND g.deleted = 'N'
            AND f.deleted = 'N'
            AND r.game_id = f.game_id
            AND r.route_id = f.route_id
            {}
            AND f.fleet_type_id = ft.fleet_type_id
            ORDER BY game_id, base_airport_iata, description
            """.format(condition)
        cursor.execute(query)
        data = cursor.fetchall()
        
        if len(data) == 0:
            return self.error(404)
        
        fields = ['game_id', 'game_id_href', 
            'base_airport_iata', 'base_airport_iata_href',
            "fleet_type_id", "fleet_type_id_href", "description", "icao_code", 
            "min_turnaround", "ops_turnaround"]
        rows = []
        for r in data:
            r['game_id_href'] = "{}/games/{}.{}".format(
                self.request.application_url, r['game_id'], 
                self.content_type)
                
            r['fleet_type_id_href'] = "{}/fleets/{}.{}".format(
                self.request.application_url, r['fleet_type_id'], 
                self.content_type)
             
            r['base_airport_iata_href'] = "{}/airports/{}.{}".format(
                self.request.application_url, r['base_airport_iata'], 
                self.content_type)
                
            rows.append(OrderedDict((key, r[key]) for key in fields))
            
        #print(rows)
        self.html_template = [{ "table_name" : "fleets", 
            "entity" : "fleet_type",
            "fields" : fields}]
            
        #self.resp.text = json.dumps(rows)
        self.resp_data = { "fleets" : rows }
        
        # get the last modification date
        query = """
        SELECT MAX(date_added) AS last_modified
        FROM flights
        WHERE game_id = {}
        AND deleted = 'N'
        """.format(game_id)
        cursor.execute(query)
        data = cursor.fetchone()
        
        self.resp.last_modified = data['last_modified'].timestamp()
        
        return self.send()
                
    """
    Create or update an existing game
    """
    def post(self):
        mode = self.urlvars.get('mode', None)
        if mode == 'airline':
            return self.post_airline()

        data = self.getJSON() #json.loads(self.request.body)
        if data is None:
            return self.error(400, "Malformed JSON")
        
        #if (not self.request.params['game_id'] or int(self.request.params['game_id']) <= 0 or not 'name' in self.request.params):
        if (int(data.get('game_id', '0')) <= 0 
         or not data.get('game_name', None)
         or not data.get('iata_code', None)):
            return self.error(400, "JSON missing fields")
        
        if not re.match('^([A-Z]{2}|[A-Z]\d|\d[A-Z])$', data['iata_code']):
            return self.error(400, "Invalid iata_code")
        
        query = '''
            INSERT IGNORE INTO games (game_id, name, iata_code) 
            VALUES ('{}', '{}', '{}')
            ON DUPLICATE KEY UPDATE 
            name=VALUES(name),
            iata_code=VALUES(iata_code),
            deleted='N'
            '''.format(data['game_id'], data['game_name'], data['iata_code'])
            
        try:
            cursor = self.get_cursor()
            cursor.execute(query)
        except Exception as e:
            print(400, e)
            
        self.db.commit()

        self.resp_data = data
        
        return self.send()
    
    
    def put(self):
        mode = self.urlvars.get('mode', None)
        if mode == 'airline':
            return self.put_airline()

        data = self.getJSON() #json.loads(self.request.body)
        if data is None:
            return self.error(400, "Malformed JSON")

        if mode == 'airline':
            return self.put_airline()
        else:
            return self.post()
            

    """
    Update airline derails for rebranding
    
    Only airline namm and IATA/ICAO codes can be changed
    """
    def put_airline(self):
        data = self.getJSON() #json.loads(self.request.body)
        if data is None:
            return self.error(400, "Malformed JSON")
        
        game_id = int(data.get('game_id', '0'))
        if game_id <= 0:
            return self.error(400, "Invalid game_id")
        
        # check whether there is already an active airline
        cursor = self.get_cursor()
        query = """
        SELECT airline_id
        FROM games g LEFT JOIN airlines a
        ON g.game_id = a.game_id
        WHERE g.game_id = {}
        AND g.deleted = 'N'
        AND a.deleted = 'N'
        """.format(game_id)
        #print(query)

        cursor.execute(query)
        res = cursor.fetchone()

        if res is None:
            return self.post_airline()
        
        if not re.match('\S+', data.get('airline_name', '')):
            return self.error(400, "Invalid JSON field airline_name")
        if not re.match(r'^([A-Z]{2}|\d[A-Z]|[A-Z]\d)$', 
            data.get('iata_code', '')):
            return self.error(400, "Invalid airline iata_code")
        if not re.match(r'^[A-Z]{3}$', data.get('icao_code', '')):
            return self.error(400, "Invalid airline icao_code")
        
        query = '''
        UPDATE airlines 
        SET name = '{}', 
        iata_code = '{}', 
        icao_code = '{}' 
        WHERE game_id = {}
        AND deleted = 'N'
        '''.format(data['airline_name'], 
                   data['iata_code'], data['icao_code'], game_id)
            
        try:
            cursor.execute(query)
        except Exception as e:
            return self.error(500, str(e))
            
        self.db.commit()
        self.resp_data = data
        
        return self.send()
    
    """
    Create new airline from request body contents. 
    
    Fail if complete data unavailable, or there is already an airline for
    this game
    """
    def post_airline(self):
        data = self.getJSON()
        if data is None:
            return self.error(400, "Malformed JSON")

        game_id = int(data.get('game_id', '0'))
        if game_id <= 0:
            return self.error(400, "Invalid game_id")
        
        # check whether there is already an active airline
        cursor = self.get_cursor()
        query = """
        SELECT airline_id
        FROM games g LEFT JOIN 
        (SELECT * FROM airlines WHERE game_id = {} AND deleted = 'N') a 
        ON g.game_id = a.game_id
        WHERE g.game_id = {}
        AND g.deleted = 'N'
        """.format(game_id, game_id)
        #print(query)

        cursor.execute(query)
        res = cursor.fetchone()

        if res is None:
            return self.error(404,"Unknown game_id {}".format(game_id))
        if res['airline_id'] is not None:
            return self.error(409, "Airline already exists")
        
        if not re.match('\S+', data.get('airline_name', '')):
            return self.error(400, "Invalid JSON field airline_name")
        if not re.match(r'^([A-Z]{2}|\d[A-Z]|[A-Z]\d)$', 
            data.get('iata_code', '')):
            return self.error(400, "Invalid airline iata_code")
        if not re.match(r'^[A-Z]{3}$', data.get('icao_code', '')):
            return self.error(400, "Invalid airline icao_code")
        if not re.match(r'^[A-Z]{3}$', data.get('base_airport_iata', '')):
            return self.error(400, "Invalid base_airport_iata")

        
        query = '''
        INSERT INTO airlines (game_id, name, base_airport_iata,
        iata_code, icao_code) 
        VALUES ({}, '{}', '{}', '{}', '{}')
        '''.format(game_id, data['airline_name'], 
            data['base_airport_iata'], data['iata_code'], data['icao_code'])
            
        try:
            cursor.execute(query)
        except Exception as e:
            return self.error(500, str(e))
            
        self.db.commit()
        self.resp_data = data
        
        return self.send()

    """
    Delete either game or airline
    """
    def delete(self):
        game_id = int(self.urlvars['game_id'])
        mode = self.urlvars.get('mode', None)

        airline_only = (mode == 'airline')
        if airline_only:
            table = "airlines"
        else:
            table = "games"
        
        # bomb if no game_id
        if (game_id < 0):
            return self.error(400)

        cursor = self.get_cursor()

        query = '''
        UPDATE {} 
        SET deleted = 'Y' 
        WHERE game_id = {}
        '''.format(table, game_id)
        cursor.execute(query)
        
        if (cursor.rowcount > 0):
            self.db.commit()
        else:
            return self.error(404)

        self.resp_data = { "deleted" : "Y" }
   
        return self.send()

GameController = rest_controller(Games)
