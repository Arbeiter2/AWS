import pymysql
from warnings import filterwarnings
filterwarnings('ignore', category = pymysql.Warning)

class AirwaysimDB:
    """create single threaded mysql db cursor"""
    def __init__(self, u='mysql', p='password', h='127.0.0.1', d='airwaysim'):
        cnx = pymysql.connect(user=u, password=p, host=h, db=d, charset='utf8')
        cursor = cnx.cursor(pymysql.cursors.DictCursor)
        #cursor = cnx.cursor(dictionary=True)

        self.cnx = cnx
        self.cursor = cursor

    def __del__(self):
        self.cursor.close()
        self.cnx.close()
        
    def getCursor(self):
        return self.cursor

    def commit(self):
        #if (self.cnx.in_transaction):
        self.cnx.commit()