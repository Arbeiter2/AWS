from datetime import timedelta
from nptools import str_to_timedelta
from mysql import connector
import math

cnx = connector.connect(user='mysql',  password='password', 
      host='localhost', database='airwaysim')
cursor = cnx.cursor(prepared=True)

updates = []

query= '''
    SELECT timetable_id, t.fleet_type_id, turnaround_length,
    base_turnaround_delta, ops_turnaround_length
    FROM fleet_types f, timetables t
    WHERE t.fleet_type_id = f.fleet_type_id
    '''
cursor.execute(query)

for row in cursor:
    t = str_to_timedelta(row[2])    
    d = str_to_timedelta(row[3])    
    o = str_to_timedelta(row[4])    

    z = t + d - o
    if z < timedelta(seconds=0):
        z = d

    #y = timedelta(seconds=math.ceil((x * 1.65).total_seconds()/300)*300)
    print(row[0], t, d, o, z)
    updates.append([z, row[0]])

query = '''
    UPDATE timetables
    SET new_delta = %s
    WHERE timetable_id = %s
    '''
for u in updates:
    #print(u)
    cursor.execute(query, u)
cnx.commit()
