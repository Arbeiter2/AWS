# -*- coding: utf-8 -*-
"""
Created on Sat Jan 21 07:29:10 2017

@author: Delano
"""
from collections import OrderedDict
import requests
import pymysql
import simplejson as json


class DataSource:
    def __init__(self, game_id):
        self.game_id = game_id

    def getBases(self):
        pass

    def getDestinations(self):
        pass
        
    def getFleets(self):
        pass

    def getFlights(self):
        pass
    
    def getTimetables(self):
        pass
    
class RESTDataSource(DataSource):
    def __init__(self, game_id, uri_base):
        super().__init__(game_id)
        
        self.uri_base = uri_base

    def getBases(self):
        uri = self.uri_base + self.game_id + "/bases"
        
        r = requests.get(uri)
        if r.status_code != 200:
            return False

        return json.loads(r.text)['airports']['bases']

    def getDestinations(self):
        uri = self.uri_base + self.game_id + "/airports"

        r = requests.get(uri)
        if r.status_code != 200:
            return False

        return json.loads(r.text)['airports']['destinations']
        
    def getFleets(self):
        uri = self.uri_base + self.game_id + "/fleets"
        
        r = requests.get(uri)
        if r.status_code != 200:
            return False

        return json.loads(r.text)['fleets']
        
    def getFlights(self):
        uri = self.uri_base + self.game_id + "/flights/basic"
        r = requests.get(uri)
        if r.status_code != 200:
            return False

        return json.loads(r.text)['flights']

    
    def getTimetables(self):
        uri =  self.uri_base + self.game_id + "/timetables/all"
        r = requests.get(uri)
        if r.status_code != 200:
            return False

        return json.loads(r.text)['timetables']

    
class DBDataSource(DataSource):
    
    def __init__(self, game_id, db_user='mysql', db_pass='password', 
                 db_host='localhost', db_name='airwaysim', db_port=3306):
        
        super().__init__(game_id)

        self.db_user = db_user
        self.db_pass = db_pass
        self.db_host = db_host
        self.db_name = db_name
        self.db_name = db_name
        self.db_port = db_port
        
        self.cnx = pymysql.connect(user=self.db_user, password=self.db_pass,
                              host=self.db_host, db=self.db_name)
        self.cursor = self.cnx.cursor(pymysql.cursors.DictCursor)

    def __getAirports__(self, mode):
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
        AND g.game_id = {}
        GROUP BY 1, 2, 4
        ORDER BY name, city
        '''.format(mode, mode, self.game_id)
        self.cursor.execute(query)

        return self.cursor.fetchall()
        
        
    def getBases(self):
        return self.__getAirports__('base')
        
    def getDestinations(self):
        return self.__getAirports__('dest')

    def getFleets(self):
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
            AND g.game_id = {}
            AND f.fleet_type_id = ft.fleet_type_id
            ORDER BY game_id, base_airport_iata, description
            """.format(self.game_id)
        self.cursor.execute(query)

        return self.cursor.fetchall()
        
    def getFlights(self):
        query = """
        SELECT DISTINCT f.game_id,
        f.route_id, f.number,
        f.flight_number,
        r.base_airport_iata,
        f.fleet_type_id,
        ft.icao_code AS fleet_type,
        r.dest_airport_iata,
        r.distance_nm,
        TIME_FORMAT(f.outbound_length, '%H:%i') AS outbound_length,
        TIME_FORMAT(f.inbound_length, '%H:%i') AS inbound_length,
        TIME_FORMAT(f.turnaround_length, '%H:%i') AS turnaround_length
        FROM flights f, routes r, games g, fleet_types ft
        WHERE f.route_id = r.route_id
        AND f.game_id = r.game_id
        AND f.game_id = g.game_id
        AND f.game_id = '{}'
        AND f.turnaround_length is not null
        AND f.fleet_type_id = ft.fleet_type_id
        AND g.deleted = 'N'
        AND f.deleted = 'N'
        GROUP BY flight_number, fleet_type_id
        ORDER BY number
        """.format(self.game_id)
        self.cursor.execute(query)

        return self.cursor.fetchall()
        
    def getTimetables(self):
        timetable_fields = ["game_id", "timetable_id", "timetable_name", 
                            "fleet_type_id", "fleet_type", "base_airport_iata", 
                            "base_turnaround_delta", "entries"]
            
        timetables = {}


        query = """
        SELECT game_id, timetable_id, last_modified, timetable_name, 
        t.fleet_type_id, base_airport_iata, ft.icao_code AS fleet_type, 
        TIME_FORMAT(base_turnaround_delta, '%H:%i') AS base_turnaround_delta
        FROM timetables t, fleet_types ft
        WHERE game_id = {}
        AND ft.fleet_type_id = t.fleet_type_id
        AND deleted = 'N'
        """.format(self.game_id)
        self.cursor.execute(query)
        
        for row in self.cursor:
            row['entries'] = []
            t = OrderedDict((key, row[key]) for key in timetable_fields)
            timetables[str(row['timetable_id'])] = t
            
        if len(timetables.keys()) == 0:
            return []
            
       
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
        '''.format(self.game_id)
        self.cursor.execute(query)
        for row in self.cursor:
            key = "{}-{}".format(row['base_airport_iata'],
                                    row['dest_airport_iata'])
            routes[key] = row['distance_nm']

        entry_fields = ["flight_number", "dest_airport_iata", 
                        "distance_nm", "start_day", "start_time", 
                        "dest_turnaround_padding", "post_padding", 
                        "earliest_available"]
            
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
        self.cursor.execute(query)
 
        for row in self.cursor:
            if not (row['flight_number'] == 'MTX'):
                key = "{}-{}".format(row['base_airport_iata'],
                                        row['dest_airport_iata'])
                row['distance_nm'] = routes[key]
            else:
                row['distance_nm'] = 0
            timetable_id = str(row['timetable_id'])

            e = OrderedDict((k, row[k]) for k in entry_fields)
            timetables[timetable_id]['entries'].append(e)
            
        return timetables.values()