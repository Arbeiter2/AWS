#!/usr/bin/python3

from webob import Request, Response
from controller import Controller, rest_controller
import simplejson as json
from decimal import Decimal
import datetime
import re
from collections import OrderedDict

num = re.compile(r"^\d+$")
icao = re.compile(r"^[A-Z0-9]{3,4}$")

def validateTime(hhmm):
    if hhmm is None:
        return False
        
    fields = hhmm.split(':')
    if len(fields) < 2:
        return False
    return ('00' <= fields[0] < '24' and '00' <= fields[1] < '60')

class Fleets(Controller):
    """manages CRUD ops on fleet types"""
    def get(self):
        """calls appropriate handler based on self.urlvars"""
        cursor = self.get_cursor()
        
        # for getting arbitrary fleet types
        fleet_type_id = self.urlvars.get('fleet_type_id', None)
        icao_code = self.urlvars.get('icao_code', None)
        
        # remove trailing slashes
        path = re.sub(r"\/+$", "", self.request.path)
            
        if fleet_type_id is not None:
            if any(not num.match(id) for id in fleet_type_id.split(";")):
                return self.error(400)
            condition = "WHERE fleet_type_id IN ({})".format(
                ", ".join(fleet_type_id.split(";")))            
        elif icao_code is not None:
            if any(not icao.match(id) for id in icao_code.split(";")):
                return self.error(400)
            condition = "WHERE icao_code IN ('{}')".format(
                "', '".join(icao_code.split(";")))
            
        query = """
        SELECT fleet_type_id, description, icao_code,
        TIME_FORMAT(turnaround_length, '%H:%i') AS turnaround_length,
        TIME_FORMAT(ops_turnaround_length, '%H:%i') AS ops_turnaround_length
        FROM fleet_types
        {}
        ORDER BY description""".format(condition)
        
        cursor.execute(query)
        
        if cursor.rowcount <= 0:
            return self.error(404)
            
        fields = ["fleet_type_id", 'fleet_type_id_href', "description", 
            "icao_code", "turnaround_length", "ops_turnaround_length"]
            
        self.html_template = [{ "table_name" : "fleet_types", 
        "entity" : "fleet_type",
            "fields" : ["fleet_type_id", "description", "icao_code", 
            "turnaround_length", "ops_turnaround_length"] }]
            
        out= []
        for x in cursor:
            x['fleet_type_id_href'] = "{}/fleets/{}.{}".format(
                self.request.application_url, x['fleet_type_id'], 
                self.content_type)
            out.append(OrderedDict((key, x[key]) for key in fields))


        self.resp_data = { "fleet_types" : out }

        return self.send()

    def put(self):
        return self.error(400)

    def post(self):
        return self.error(400)
        
 
FleetController = rest_controller(Fleets)
