import controller

class Root(object):
    def __init__(self, req):
        self.request = req

    def __cursor(self):
        if not self.cursor:
            self.db = aws_db.AirwaysimDB()
            self.cursor = self.db.getCursor()
        return self.cursor
        
    def get(self):
        resp = controller.Response()
        resp.content_type = 'text/plain'
        resp.charset = 'utf8'
        resp.text = str(self.request.body)        
        return resp

    def post(self):
        resp = controller.Response()
        resp.content_type = 'text/plain'
        resp.charset = 'utf8'
        resp.text = str(self.request.body)

        return resp


    def delete(self):
        resp = controller.Response()
        resp.content_type = 'text/plain'
        resp.charset = 'utf8'
        resp.text = str(self.request.body)

        return resp

RootController = controller.rest_controller(Root)