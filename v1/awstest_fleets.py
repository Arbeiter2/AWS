from webob import Request, Response
from router import Router
import aws_fleets
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
    '/fleets/@fleet_type_id:\d+(;\d+)*@', # GET
    '/fleets/icao/@icao_code:\w+(;\w+)*@', # GET
    '/fleets', # GET, POST
    ],
   controller=aws_fleets.FleetController)

   
req1 = Request.blank("/fleets/icao/A380;SB20")
req1.method = 'GET'
#req1.accept = "application/json; q=0.5, text/html;q=1"
req1.accept = "text/html;q=1"
resp1 = req1.get_response(main)
print(resp1)
