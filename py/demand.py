from mysql import connector
import math
import json

cnx = connector.connect(user='mysql',  password='password', 
      host='localhost', database='airwaysim')
cursor = cnx.cursor(dictionary=True)

updates = []
f = open('c:/tmp/airports.json', 'w')
f.write("allAirports = [\n");
query= '''
    SELECT DISTINCT iata_code, icao_code
    from airports a, routes r
    where r.dest_airport_iata = a.iata_code
    and r.game_id = 155
    and continent in ('AS', 'AF', 'EU')
    and iata_code not in (
    SELECT iata_code from airport_curfews)
    order by 1
'''
cursor.execute(query)
for m in cursor:
    f.write(json.dumps(m) + ",\n")
    #print(m, str(m[0].decode('utf_8')))

#rows = cursor.fetchall()
#print(rows)
#print("', '".join(str(i) for i in rows))
#print(",\n".join(updates))
f.write("];\n");
f.close()
