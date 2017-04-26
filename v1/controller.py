from webob import Request, Response
from webob import exc
import aws_db
import simplejson as json
import re
from collections import Iterable
from table_builder import get_html, get_xml

def sortDictList(key, dicts):
    if not isinstance(dicts, Iterable):
        return None
        
    # fail if any list member is not a dict, or key not in dict
    if not all((isinstance(x, dict) and key in x) for x in dicts):
        return None
    
    decorated = [(x[key], x) for x in dicts]
    decorated.sort()
    return [x for (key, x) in decorated]
            
def rest_controller(cls):
    def replacement(environ, start_response):
        req = Request(environ)
        try:
            instance = cls(req, **req.urlvars)
            if not instance.valid:
                raise exc.HTTPBadRequest()
            action = req.urlvars.get('action')
            if action:
                action += '_' + req.method.lower()
            else:
                action = req.method.lower()
            try:
                method = getattr(instance, action)
            except AttributeError:
                raise exc.HTTPNotFound("No action %s" % action)

            resp = method()
            if isinstance(resp, str):
                resp = Response(body=resp)

        except exc.HTTPException as e:
            resp = e
        return resp(environ, start_response)
    return replacement

class Controller(object):
    def __init__(self, req, **urlvars):
        self.request = req
        self.urlvars = urlvars
        self.db = None
        self.cursor = None

        self.resp = Response(conditional_response=False)
        self.resp.content_type = 'application/json'
        self.content_type = 'json'
        self.valid = True
        
        # remove trailing slashes from path
        path = re.sub(r"\/+$", "", self.request.path)
        #print("path = [%s]" % path,  re.match(r".html$", path))

        
        # only send text/html for GET requests where application/json is not
        # acceptable, but text/html is
        #if (self.request.method == "GET"
        #and 'application/json' not in self.request.accept
        #and 'text/html' in self.request.accept):
        m = re.search(r"\.(html|xml|json)$", path)
        if m:
            type = m.group(1)
            if self.request.method != "GET":
                self.valid = False
            else:
                if type == 'html' and 'text/html' in self.request.accept:
                    self.content_type = 'html'
                    self.resp.content_type = 'text/html'
                elif type == 'xml' and 'application/xml' in self.request.accept:
                   self.content_type = 'xml'
                   self.resp.content_type = 'application/xml'          
        self.resp.charset = 'utf8'
        #self.resp.text = '{}'
        #self.resp.cache_control.max_age = 300
        self.resp.cache_expires(0)
        self.resp_data = None
        self.html_template = None
        
    def get_cursor(self):
        if not self.cursor:
            self.db = aws_db.AirwaysimDB()
            self.cursor = self.db.getCursor()
        return self.cursor
        
    def get(self):
        return self.resp
        
    def post(self):
        return self.resp

    def delete(self):
        return self.resp
        
    def send(self):
        if self.content_type == 'html':
            self.resp.text = get_html(self.resp_data, self.html_template)
        elif self.content_type == 'xml':
            self.resp.text = get_xml(self.resp_data, self.html_template)
        else:   # default type is json
            self.resp.text = (json.dumps(self.resp_data)
                                  .encode('utf-8')
                                  .decode('unicode_escape'))

        # always set etag for cache_control
        self.resp.md5_etag()

        # force gzip encoding if accepted by client
        if (self.request.accept_encoding and
            re.search("gzip", str(self.request.accept_encoding))):
            self.resp.encode_content(encoding='gzip')
        return self.resp
        
    def error(self, status=400, errorStr=None):
        if errorStr is not None:
            error_text = {}
            error_text['error'] = errorStr
            self.resp.text = json.dumps(error_text)
        self.resp.status = status

        if status == 404:
            raise exc.HTTPNotFound(self.resp.text)
        elif status == 400:
            raise exc.HTTPBadRequest(self.resp.text)
        elif status == 500:
            raise exc.HTTPServerError(self.resp.text)
        
        return self.resp
        
