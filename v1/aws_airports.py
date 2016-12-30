#!/usr/bin/python3

from webob import Request, Response
from controller import Controller, rest_controller
import simplejson as json
from decimal import Decimal
import datetime
from collections import OrderedDict
import re

def validateTime(hhmm):
    if hhmm is None:
        return False
        
    fields = hhmm.split(':')
    if len(fields) < 2:
        return False
    return ('00' <= fields[0] < '24' and '00' <= fields[1] < '60')

class Airports(Controller):
    """manages CRUD ops on Airports"""
    def get(self):
        """calls appropriate handler based on self.urlvars"""
        cursor = self.get_cursor()
        
        # for getting arbitrary flights
        iata_code = self.urlvars.get('iata_code', None)
        icao_code = self.urlvars.get('icao_code', None)
        
        # remove trailing slashes
        path = re.sub(r"\/+$", "", self.request.path)
        
        curfew_only = (path.split("/")[-1:][0] == 'curfew')
        
        if (iata_code is not None):
            condition = "a.iata_code IN ('{}')".format(
                "', '".join(re.split("[;,]", iata_code)))
        elif icao_code is not None:
            condition = "a.icao_code IN ('{}')".format(
                "', '".join(re.split("[;,]", icao_code)))
        else:
            # bad request
            return self.error(400)


        query = """SELECT a.iata_code, a.icao_code, city,
        airport_name, country, timezone, 
        TIME_FORMAT(start, '%H:%i') AS curfew_start, 
        TIME_FORMAT(finish, '%H:%i') AS curfew_finish
        FROM airports a LEFT JOIN airport_curfews c
        ON a.iata_code = c.iata_code
        WHERE {}""".format(condition)
        
        cursor.execute(query)
        
        data = cursor.fetchall()
        if len(data) == 0:
            return self.error(404)
            
        #print(rows)
        
        self.html_template = [{ "table_name" : "airports", 
        "entity" : "airport",
        "fields" : [ "iata_code", "icao_code", "city", "airport_name", 
            "country", "timezone", 'curfew_start', 'curfew_finish' ] }]
        
        # remove empty curfew fields
        rows = []
        std_fields = ["iata_code", "iata_code_href", "icao_code", 
            "icao_code_href", "city", "airport_name", "country", "timezone" ]
        curfew_fields = ["curfew_start", "curfew_finish"]
        for x in data:
            x["icao_code_href"] = ("{}/airports/{}.{}").format(
                self.request.application_url, x["icao_code"], self.content_type)

            x["iata_code_href"] = ("{}/airports/{}.{}").format(
                self.request.application_url, x["iata_code"], self.content_type)

            # return an empty json object if there is no curfew
            if curfew_only:
                d = OrderedDict((key, x[key]) for key in curfew_fields)
            else:
                d = OrderedDict((key, x[key]) for key in std_fields)
                if validateTime(x['curfew_start']):
                    d['curfew_start'] = x['curfew_start']
                    d['curfew_finish'] = x['curfew_finish']
                    
            rows.append(d)
            
        self.resp_data = { "airports" : rows }
            
        #self.resp.text=json.dumps(rows).encode('utf-8').decode('unicode_escape')
        self.resp.status = 200

        return self.send()

    def put(self):
        return self.createCurfew()

    def post(self):
        return self.createCurfew()
        
    def createCurfew(self):
        """allows changes to curfew times only"""
        cursor = self.get_cursor()
        
        # remove trailing slashes from PATH_INFO
        path = re.sub(r"\/+$", "", self.request.path)
        
        # only valid for resource URIs ending in /curfew or /curfew/
        if not any(x == 'curfew' for x in path.split("/")[-3:]):
            return self.error(400)
        
        # either is acceptable
        iata_code = self.urlvars.get('iata_code', None)
        icao_code = self.urlvars.get('icao_code', None)
        
        if (iata_code is not None):
            condition = "a.iata_code = '{}'".format(iata_code)
        elif icao_code is not None:
            condition = "a.icao_code = '{}'".format(icao_code)
        else:
            # bad request
            return self.error(400, "No airport code provided")
            
        # look for the start and finish values in three (3) places:
        
        # PATH_INFO: /start/finish e.g. /airports/LHR/23:00/06:00
        curfew_finish = self.urlvars.get('finish', None)
        curfew_start = self.urlvars.get('start', None)

        
        # POST: in form variables
        if (curfew_start is None and curfew_finish is None):
            curfew_finish = self.request.POST.get('finish', None)
            curfew_start = self.request.POST.get('start', None)    
        
        # body: in JSON e.g. '{ "start" : "23:00", "finish" : "06:00" }'
        if (curfew_start is None and curfew_finish is None):
            # get json
            try:
                data = json.loads(self.request.body)
            except ValueError as e:
                return self.error(400, "No curfew start/finish times provided")
            
            if isinstance(data, dict):
                curfew_finish = data.get('finish', None)
                curfew_start = data.get('start', None)
            else:
                return self.error(400, 
                    "No curfew start/finish times in request body")
        
        if (not validateTime(curfew_start) 
        or not validateTime(curfew_finish)
        or curfew_start == curfew_finish):
            # bad request
            return self.error(400, "Bad time(s) provided for curfew")
            
        query = """SELECT a.iata_code, a.icao_code, city,
        airport_name, country, timezone, start as curfew_start,
        finish as curfew_finish
        FROM airports a LEFT JOIN airport_curfews c
        ON a.iata_code = c.iata_code
        WHERE {}""".format(condition)
        
        cursor.execute(query)
        
        x = cursor.fetchall()
        if len(x) == 0:
            return self.error()
        
        x = x[0]
        query = """
        INSERT INTO airport_curfews (iata_code, icao_code, start, finish)
        VALUES ('{}', '{}', '{}', '{}')
        ON DUPLICATE KEY UPDATE
        start = VALUES(start),
        finish = VALUES(finish)
        """.format(x['iata_code'], x['icao_code'], curfew_start, curfew_finish)
        
        cursor.execute(query)
        self.db.commit()

        self.resp.status = 200

        return self.send()

        
    def delete(self):
        """allows changes to curfew times only"""
        cursor = self.get_cursor()
        
        # for getting arbitrary flights
        iata_code = self.urlvars.get('iata_code', None)
        icao_code = self.urlvars.get('icao_code', None)

        if (iata_code is not None):
            condition = "a.iata_code = '{}'".format(iata_code)
        elif icao_code is not None:
            condition = "a.icao_code = '{}'".format(icao_code)
        else:
            # bad request
            return self.error()
            
        query = """SELECT a.iata_code, a.icao_code, city,
        airport_name, country, timezone, start as curfew_start,
        finish as curfew_finish
        FROM airports a LEFT JOIN airport_curfews c
        ON a.iata_code = c.iata_code
        WHERE {}""".format(condition)
       
        cursor.execute(query)
        
        x = cursor.fetchall()
        if len(x) == 0:
            return self.error(404)
      
        x = x[0]
        query = """
        UPDATE airport_curfews 
        SET start = NULL, finish = NULL
        WHERE iata_code = '{}'""".format(x['iata_code'])

        cursor.execute(query)
        self.db.commit()

        self.resp.status = 200

        return self.send()
        
AirportController = rest_controller(Airports)
