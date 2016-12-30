import re
# this pattern does not permit curly braces in  the regex part
var_regex = re.compile(r'''
    \{          # The exact character "{"
    (\w+)       # The variable name (restricted to a-z, 0-9, _)
    (?::([^}]+))? # The optional :regex part
    \}          # The exact character "}"
    ''', re.VERBOSE)

# this pattern permits curly braces in  the regex part
var_regex2 = re.compile(r'''
    \@          # The exact character "@"
    (\w+)       # The variable name (restricted to a-z, 0-9, _)
    (?::([^@]+))? # The optional :regex part
    \@          # The exact character "@"
    ''', re.VERBOSE)    
    
def template_to_regex(template):
    regex = ''
    last_pos = 0
    for match in var_regex2.finditer(template):
        regex += re.escape(template[last_pos:match.start()])
        var_name = match.group(1)
        expr = match.group(2) or '[^/]+'
        expr = '(?P<%s>%s)' % (var_name, expr)
        regex += expr
        last_pos = match.end()
        
    regex += re.escape(template[last_pos:])
    if template[-1] == '/':
        regex = '^%s$' % regex
    else:
        regex = '^%s([\/]|\.html|\.json|\.xml)?$' % regex # allow trailing slashes
    return regex

import sys
def load_controller(string):
    module_name, func_name = string.split(':', 1)
    __import__(module_name)
    module = sys.modules[module_name]
    func = getattr(module, func_name)
    return func

from webob import Request
from webob import exc
 
class Router(object):
    def __init__(self):
        self.routes = []

    def add_route(self, templates, controller, **vars):
        '''can register multiple templates to a single controller'''
        if isinstance(controller, str):
            controller = load_controller(controller)

        if not isinstance(templates, list):
            templates = [templates]
            
        for tmplt in templates:
            self.routes.append((re.compile(template_to_regex(tmplt)),
                                controller,
                                vars))

    def __call__(self, environ, start_response):
        req = Request(environ)
        for regex, controller, vars in self.routes:
            match = regex.match(req.path_info)
            if match:
                req.urlvars = match.groupdict()
                req.urlvars.update(vars)
                return controller(environ, start_response)
        return exc.HTTPNotFound()(environ, start_response)