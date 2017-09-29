from aws_db import AirwaysimDB

db = AirwaysimDB()
cursor = db.getCursor()
#query = """SELECT DISTINCT SUBSTRING(flight_number, 3) AS flight_number
#FROM flights
#WHERE game_id = 190
#AND deleted = 'N'"""
query = """SELECT DISTINCT number
FROM flights
WHERE game_id = 206
AND deleted = 'N'"""
cursor.execute(query)

existing = []
for r in cursor:
	existing.append(int(r['number']))
    
max_num = max(existing)
full = range(1, max_num + 2, 2)
print(list(filter(lambda x: x not in existing, full)))
