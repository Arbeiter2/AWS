from webob import Request, Response
from controller import Controller, rest_controller, sortDictList
import simplejson as json
import re
from decimal import Decimal
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

        query = """
        SELECT game_id, name
        FROM games 
        WHERE game_id IN ('{}') 
        AND deleted = 'N'""".format("', '".join(re.split(r"[;,]", game_id)))
        cursor = self.get_cursor()
        cursor.execute(query)
        if cursor.rowcount <= 0:
            return self.error(404)
            
        # base data
        for row in cursor:
            out = OrderedDict()
            out['name'] = row['name']
            out['game_id'] = row['game_id']
            
            out['bases'] = "{}/games/{}/bases.{}".format(
                self.request.application_url, row['game_id'], self.content_type)
            out['bases_href'] = out['bases']

            # flight data
            out['flights'] = "{}/games/{}/flights.{}".format(
                    self.request.application_url, row['game_id'], self.content_type)
            out['flights_href'] = out['flights']
            
            # timetable data
            out['timetables'] = "{}/games/{}/timetables.{}".format(
                    self.request.application_url, row['game_id'], self.content_type)
                    
            out['timetables_href'] = out['timetables']        

            res.append(out)

        self.html_template = [{"table_name" : "games", 
        "entity" : "game",
            "fields" : ["game_id", "name", "bases", "flights", "timetables"],
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
        SELECT DISTINCT g.game_id, g.name, MAX(r.date_added) AS date_added,
        r.{}_airport_iata as iata_code, a.icao_code, a.timezone, a.city, 
        a.airport_name,
        TIME_FORMAT(c.start, '%H:%i') AS curfew_start,
        TIME_FORMAT(c.finish, '%H:%i') AS curfew_finish
        FROM games g, routes r, flights f,
        airports a LEFT JOIN airport_curfews c
        ON a.icao_code = c.icao_code
        WHERE r.game_id = f.game_id
        AND r.route_id = f.route_id
        AND r.game_id = g.game_id
        AND r.{}_airport_iata = a.iata_code
        AND f.deleted = 'N'
        AND g.deleted = 'N'
        {}
        GROUP BY 1, 2, 4
        ORDER BY name, city
        '''.format(mode, mode, condition)
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
                
            if r['date_added'] is not None and r['date_added'] > last_modified:
                last_modified = r['date_added']
            del r['date_added']
                
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
 
        out = sortDictList("name", games.values())
                    
        #self.resp.text = json.dumps(out, encoding="ISO-8859-1")
        self.html_template = [{ "table_name" : "airports",
            "entity" : "game",
            "fields" : ["game_id", "name", 
            {"table_name" : label, "entity" : "airport",
            "fields" : [ 'iata_code', 'icao_code', 'city', 'airport_name', 
            'timezone', 'curfew_start', 'curfew_finish']}],
            "stacked_headers" : True }]
            
        self.resp_data = { "airports" : out }
        print(last_modified)
        self.resp.last_modified = last_modified.timestamp()
            
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
                
    def post(self):
        data = json.loads(self.request.body)
        
        #if (not self.request.params['game_id'] or int(self.request.params['game_id']) <= 0 or not 'name' in self.request.params):
        if (int(data.get('game_id', '0')) <= 0 or data.get('name', '') == ''):
            return self.error(400)
        else:
            query = '''
                INSERT IGNORE INTO games (game_id, name) 
                VALUES ('{}', '{}')
                ON DUPLICATE KEY UPDATE 
                name=VALUES(name),
                deleted='N'
                '''.format(
                data['game_id'], 
                data['name'])

            cursor = self.get_cursor()
            
            try:
                cursor.execute(query)
                obj = { 'game_id': data['game_id'], 
                        'name': data['name'], 
                        'deleted': 'N' 
                      }
                
            except aws_db.Error as err:
                return self.error(500, err)
                

        self.resp_data = obj
        
        return self.send()


    def delete(self):
        game_id = int(self.urlvars['game_id'])
        
        # bomb if no game_id
        if (game_id < 0):
            return self.error(400)

        cursor = self.get_cursor()

        query = '''
        UPDATE games 
        SET deleted = 'Y' 
        WHERE game_id = {}
        '''.format(game_id)
        cursor.execute(query)
        
        if (cursor.rowcount > 0):
            self.db.commit()
        else:
            return self.error(404)

        self.resp_data = { "deleted" : "Y" }
   
        return self.send()

GameController = rest_controller(Games)
