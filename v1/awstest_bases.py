from webob import Request
from router import Router
import aws_games

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
                    '/games',
                    '/games/@bases:(bases)@',
                    '/games/@game_id:\d+([;,]\d+)*@',
                    '/games/@game_id:\d+@/@mode:(fleets|bases|airports)@',
            ],
               controller=aws_games.GameController)


    
#for path in ['/games/bases.xml', '/games/155/fleets', '/games/155.html', '/games.xml' ]:
#for path in ['/games/bases']:
#   req2 = Request.blank(path)
   #req2.accept = "application/json; q=0.5, text/html;q=1"
   #req2.accept = "text/html;q=1"   
#   resp2 = req2.get_response(main)
#   print(resp2)

req2 = Request.blank('/games')
req2.method = 'POST'
req2.body = b'{ "name" : "Test game", "game_id" : 1000, "iata_code" : "ZZ" }'
resp2 = req2.get_response(main)
print(resp2)