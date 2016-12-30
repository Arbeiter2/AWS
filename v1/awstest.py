from webob import Request, Response
from router import Router
from controller import rest_controller
import aws_games
import aws_bases

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
main.add_route('/games', controller=aws_games.GameController)
main.add_route('/games/{game_id:\d+}', controller=aws_games.GameController)
main.add_route([
                '/games/{game_id:\d+}/{bases}',
                '/flights/{game_id:\d+}/{bases}',
                '/bases/{game_id:\d+}'
               ],
               controller=aws_bases.BaseController)

#req1 = Request.blank('/games')
#resp1 = req1.get_response(main)

req2 = Request.blank('/games')
req2.method = 'POST'
req2.body = bytes('{ "name" : "Test game", "game_id" : 1000 }', 'utf8')
resp2 = req2.get_response(main)
print(resp2)

#req3 = Request.blank('/flights/155/bases')
#req3.method = 'GET'
#resp3 = req3.get_response(main)
#print(resp3)
