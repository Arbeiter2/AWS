#!/usr/bin/python3

from webob import Request, Response
from router import Router
import aws_airports

try:
    unicode = unicode
except NameError:
    # 'unicode' is undefined, must be Python 3
    str = str
    unicode = str
    bytes = bytes
    basestring = (str,bytes)
else:
    # 'unicode' exists, must be Python 2
    str = str
    unicode = unicode
    bytes = str
    basestring = basestring

main = Router()
main.add_route([
    '/airports/@iata_code:[A-Z]{3}([,;][A-Z]{3})*@',               # GET
    '/airports/@icao_code:[A-Z]{4}([,;][A-Z]{4})*@',               # GET
    '/airports/@iata_code:[A-Z]{3}@/curfew',        # GET, POST, PUT, DELETE
    '/airports/@icao_code:[A-Z]{4}@/curfew',        # GET, POST, PUT, DELETE
    '/airports/@iata_code:[A-Z]{3}@/curfew/@start:\d{2}:\d{2}@/@finish:\d{2}:\d{2}@',  # PUT
    '/airports/@icao_code:[A-Z]{4}@/curfew/@start:\d{2}:\d{2}@/@finish:\d{2}:\d{2}@',  # PUT

            ],
               controller=aws_airports.AirportController)


    
#req2 = Request.blank('/airports/FRA')
#req2.method = 'GET' 
#resp2 = req2.get_response(main)
#print(resp2)

req3 = Request.blank('/airports/POS/curfew')
req3.method = 'POST' 
req3.body = bytes('{ "start": "00:30", "finish" : "06:00" }', 'utf-8')
#resp3 = req3.get_response(main)
#print(resp3)

req2 = Request.blank('/airports/LAX,MME,SIN.xml')
req2.method = 'GET' 
#req2.accept = "application/json; q=0.5, text/html;q=1"
#req2.accept = "text/html;q=1"
resp2 = req2.get_response(main)
print(resp2)

req2 = Request.blank('/airports/POS/curfew')
#req2.method = 'DELETE' 
#resp2 = req2.get_response(main)
#print(resp2)

req2 = Request.blank('/airports/POS;BGI;BIO/curfew')
req2.method = 'GET' 
#resp2 = req2.get_response(main)
#print(resp2)
