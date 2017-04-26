#!/usr/bin/python3
from webob import Response
from controller import Controller, rest_controller
import simplejson as json

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
        
        resp = Response()
        resp.content_type = 'application/json'
        resp.charset = 'utf8'
        resp.status = 200
        resp.text = '{}'
        
        # for getting arbitrary flights
        iata_code = self.urlvars.get('iata_code', None)
        icao_code = self.urlvars.get('icao_code', None)

        
        if (iata_code is not None):
            condition = "a.iata_code = {}".format(iata_code)

        elif icao_code is not None:
            condition = "a.icao_code = {}".format(icao_code)
        else:
            # bad request
            resp.status = 400
            return resp
            
        query = """SELECT a.iata_code, a.icao_code, city,
        airport_name, country, timezone, start as curfew_start,
        finish as curfew_finish
        FROM airports a LEFT JOIN airport_curfews c
        ON a.iata_code = c.iata_code
        WHERE""".format(condition)
        cursor.execute(query)
        
        x = cursor.fetchall()
        if len(x) == 0:
            resp.status = 404
            return resp
            
        # remove empty curfew fields
        if not validateTime(x['curfew_start']):
            del x['curfew_start']
            del x['curfew_finish']
            
        resp.text = json.dumps(x[0])

        return resp

    def put(self):
        """allows changes to curfew times only"""
        cursor = self.get_cursor()
        
        # for getting arbitrary flights
        iata_code = self.urlvars.get('iata_code', None)
        icao_code = self.urlvars.get('icao_code', None)
        curfew_finish = self.urlvars.get('finish', None)
        curfew_start = self.urlvars.get('start', None)
        
        if (iata_code is not None):
            condition = "a.iata_code = {}".format(iata_code)
        elif icao_code is not None:
            condition = "a.icao_code = {}".format(icao_code)
        else:
            # bad request
            return self.error(400)
            
        if (not validateTime(curfew_start) 
        or not validateTime(curfew_finish)
        or curfew_start == curfew_finish):
            # bad request
            return self.error(400)
            
        query = """SELECT a.iata_code, a.icao_code, city,
        airport_name, country, timezone, start as curfew_start,
        finish as curfew_finish
        FROM airports a LEFT JOIN airport_curfews c
        ON a.iata_code = c.iata_code
        WHERE""".format(condition)
        cursor.execute(query)
        
        x = cursor.fetchall()
        if len(x) == 0:
            return self.error(400)

        query = """
        INSERT INTO airport_curfews (iata_code, icao_code, start, finish)
        VALUES ('{}', '{}', '{}', '{}')
        ON DUPLICATE KEY UPDATE
        curfew_start = VALUES(curfew_start),
        curfew_finish = VALUES(curfew_finish)
        """.format(x['iata_code'], x['icao_code'], curfew_start, curfew_finish)
        
        cursor.execute(query)

        self.resp.status = 200

        return self.resp

        
    def delete(self):
        return self.error(400)
        
AirportController = rest_controller(Airports)