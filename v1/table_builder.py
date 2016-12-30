import re
import simplejson as json
from collections import OrderedDict
from xml.sax.saxutils import escape

validXmlElement = re.compile(r"^(?!xml)[a-zA-Z]+[a-zA-Z-_\.]+$", re.I)


def collapse_uris(data, leave_href=False):
    if not isinstance(data, list):
        newData = [data]
    else:
        newData = data
    for d in newData:
        uri_list = []    
        # build llnks from hrefs
        # if we see data['x'] and data['x_href'], we replace data['x'] with
        # and html anchor of the form
        # <a href="data['x_href']" target="_blank">data['x']</a>
        # e.g. 
        # data['flight_number'] = "AV001", 
        # data['flight_number_href'] = "/games/155/flights/AV001/basic"
        # => data['flight_number'] = 
        # <a href="/games/155/flights/AV001/basic" target="_blank">AV001</a>
        for key in d:
            # escape all non-URI fields
            if key + "_href" in d and key not in uri_list:
                d[key] = '<a href="{}" target="_blank">{}</a>'.format(
                    d[key + "_href"], d[key])
                uri_list.append(key)
            if (isinstance(d[key], str) and not re.match(r"href", key) 
            and key not in uri_list):
                d[key] = escape(d[key]).encode('ascii', 
                    'xmlcharrefreplace').decode(encoding='UTF-8')
                    
def get_inner_xml(data, template):
    if data is None or template is None:
        return ""

    if any(x not in template for x in ["table_name", "fields", "entity"]):
        #print('Data incomplete: missing one of "table_name", "fields", "entity"')
        return ""
        
    # root and entity names must be valid
    if not all(validXmlElement.match(template[x])
        for x in ["table_name", "entity"] ):
        #print('Invalid element names:\n{}'.format(template))
        return ""
 
    # element names must be valid
    if not all( isinstance(x, dict) or validXmlElement.match(x) 
        for x in template["fields"]):
        #print('Invalid element names\n{}'.format(template["fields"]))
        return ""
        
    if (template["table_name"] not in data):
        #print("{} not in data\n{}".format(template["table_name"], data))
        return ""

    out = "<{}>".format(template["table_name"])
    if template["table_name"] in data:
        #print("{}\n{}\n{}\n".format(json.dumps(data, indent=4), template, template["table_name"]))
        inner_data = data[template["table_name"]]
        if not isinstance(inner_data, list):
            inner_data = [inner_data]
        for d in inner_data: # data[template["table_name"]]:
            #print(d)
            out += "<{}>".format(template["entity"])
            for f in template["fields"]:
                if isinstance(f, str):
                    if not isinstance(d, dict):
                        print("Bad data: missing {}\n{}".format(d, data))
                    out += "<{}>{}</{}>".format(f, d.get(f, ""), f)
                    #if f + "_href" in d:
                    #    href = f + "_href"
                    #    out += "<{}>{}</{}>".format(href, d[href], href)
                elif isinstance(f, dict):
                    out += get_inner_xml(d, f)
            out += "</{}>".format(template["entity"])
    out += "</{}>".format(template["table_name"])
    
    return out

def get_xml(data, template):
    out = '<?xml version="1.0" encoding="UTF-8" ?>'
    if not isinstance(template, list):
        template = [template]

    for t in template:
        out += get_inner_xml(data, t)
    
    return out
    

# def get_table(data, template, with_caption=True):
    # """
    # create HTML table from data provided, using template thus:

    # <template> := dict("table_name": <str>, "fields": [<field>, ...], 
                # "stacked_headers" : <bool> (default: False),
                # "optional" : [<str>, ...])
                
    # <field> := <str> | <template>
    
    # This allows nested tables, by putting the template for the nested
    # table in the list.

    # If "stacked_headers" is True, table is created with header column 
    # to the left, data to the right. Default (False) results in header row.
    
    # """
    # if data is None or template is None:
        # return None
        
    # if not isinstance(data, list):
        # data = [data]
        
    # if any(x not in template for x in ["table_name", "fields",]):
        # return None
        
    # caption = ""
    # if with_caption:
        # caption = "<caption>{}</caption>\n".format(template["table_name"])
    
    # thead = ""
    # thead_row2 = ""
    # t = ""
    # cols = []
    # stacked_headers = template.get("stacked_headers", False)

    # # for standard (non-stacked) table, create single table from all data
    # if not stacked_headers:
        # thead = "<tr>\n"
        # rowspan = 1
        # if any(isinstance(x, dict) and "optional" in x and not x["optional"] 
            # for x in template["fields"]):
            # t = "<th rowspan='2'></th>\n"
            # rowspan = 2
            # thead_row2 = "<tr>\n"

        # # build thead <th> cells
        # for f in template["fields"]:
            # if isinstance(f, str):
                # thead += "<th rowspan='{}'>{}</th>\n".format(rowspan, f.replace("_", "<br>"))
                # cols.append(1)
            # elif (isinstance(f, dict) 
            # and "table_name" in f and isinstance(f["table_name"], str)
            # and "fields" in f and isinstance(f["fields"], list)):
                # optional = f.get("optional", False)
                # if not optional:
                    # thead += "<th colspan='{}' scope='colgroup'>{}</th>\n".format(
                        # len(f["fields"]), f["table_name"])
                    # cols.append(len(f["fields"]))
                    
                    # thead_row2 += "\n".join(
                        # ["<th>{}</th>".format(fld) for fld in f["fields"]])
                # else:
                    # thead += "<th rowspan='{}'>{}</th>\n".format(
                        # rowspan, f["table_name"].replace("_", "<br>"))
            # else:
                # return None
        # thead += "</tr>\n\n"

        # # build <col> and complete thead
        # colstring = ""
        # if rowspan == 2:
            # colstring = "<col>\n"
            # for s in cols:
                # colstring += "<colgroup span='{}'></colgroup>\n".format(s)
            # thead_row2 += "\n</tr>\n\n"
            # thead += thead_row2

        # t = """
# <table class='simple'>
# {}
# {}
# <thead>
# {}
# </thead>\n""".format(caption, colstring, thead)            

    # for d in data:
        # uri_list = []    
        # # build llnks from hrefs
        # # if we see data['x'] and data['x_href'], we replace data['x'] with
        # # and html anchor of the form
        # # <a href="data['x_href']" target="_blank">data['x']</a>
        # # e.g. 
        # # data['flight_number'] = "AV001", 
        # # data['flight_number_href'] = "/games/155/flights/AV001/basic"
        # # => data['flight_number'] = 
        # # <a href="/games/155/flights/AV001/basic" target="_blank">AV001</a>
        # for key in d:
            # # escape all non-URI fields
            # if key + "_href" in d and key not in uri_list:
                # d[key] = '<a href="{}" target="_blank">{}</a>'.format(
                    # d[key + "_href"], d[key])
                # uri_list.append(key)
            # if (isinstance(d[key], str) and not re.match(r"href", key) 
            # and key not in uri_list):
                # d[key] = escape(d[key]).encode('ascii', 
                    # 'xmlcharrefreplace').decode(encoding='UTF-8')
            # if re.match(r"_href", key):
                # d[key] = '<a href="{}" target="_blank">{}</a>'.format(
                    # d[key], d[key])

    # if not stacked_headers:
        # for d in data:
            # #print(json.dumps(d, indent=4), template )
            # # for standard table
            # rowspan = 1
            # remaining_rows = []
            # tds = []
            # for f in template["fields"]:
                # if isinstance(f, str):
                    # # puts blank space for missing fields
                    # tds.append({ "text" : format(d.get(f, "&nbsp;")), 
                        # "rowspan" : rowspan })
                # elif isinstance(f, dict):
                    # optional = f.get("optional", False)
                    # # missing mandatory field
                    # if not optional and f["table_name"] not in d:
                        # raise Exception("Missing {}".format(f["table_name"]))
                        
                    # if optional:
                        # if f["table_name"] not in d:
                            # tds.append({ "text" : "&nbsp;", "rowspan" : rowspan })
                        # else:
                            # tds.append({
                                # "text" : get_table(d[f["table_name"]], f, False),
                                # "rowspan" : rowspan})
                    # else:
                        # if isinstance(d[f["table_name"]], list):
                            # #print(json.dumps(d[f["table_name"]], indent=4))
                            # if len(d[f["table_name"]]) > 0:
                                # rowspan = max([len(d[f["table_name"]]), rowspan])
                                # tds.extend([ { "text" : format(d[f["table_name"]][0][x]), "rowspan" : 0 }
                                    # for x in f["fields"] ])

                                # if len(remaining_rows) <= rowspan - 1:
                                    # remaining_rows.extend([[]] * (rowspan - 1 - len(remaining_rows)))
                                    # for idx in range(1, len(d[f["table_name"]])):
                                        # remaining_rows[idx - 1].extend(
                                        # [ { "text" : format(d[f["table_name"]][idx][x]), "rowspan" : 0 }
                                        # for x in f["fields"] ])
                                        # #print(idx, rowspan, remaining_rows[idx - 1])

                                    # #print(remaining_rows)
                            # else:
                                # tds.append({ "text" : "&nbsp;", "rowspan" : 0 })
                        # else:
                            # tds.extend([ { "text" : format(d[f["table_name"]][x]), "rowspan" : 0 }
                                # for x in f["fields"] ])
            
            # # main 
            # #print(remaining_rows)
            # t += "<tr>\n"
            # for td in tds:
                # t += "<td"
                # if td["rowspan"] > 0:
                    # t += " rowspan='{}'>".format(rowspan)
                # else:
                    # t += ">"
                # t += td["text"]
                # t += "</td>\n"
            # t += "</tr>\n\n"
            
            # # add remaining rowspan
            # for tr in remaining_rows:
                # #print(tr)
                # t += "<tr>\n"
                # for td in tr:
                    # t += "<td>"
                    # t += td["text"]
                    # t += "</td>\n"
                # t += "</tr>\n\n"
                
                
        # t += "</table>"
    # else:
        # for d in data:
            # t += "<table class='simple'>\n"
            # for f in template["fields"]:
                # t += "<tr>\n"
                # if isinstance(f, str):
                    # t += "<th>{}</th>\n".format(f)
                    # t += "<td>{}</td>\n".format(d[f])
                # elif (isinstance(f, dict) # f is a template
                # and "table_name" in f and isinstance(f["table_name"], str)
                # and "fields" in f and isinstance(f["fields"], list)):
                    # t += "<th>{}</th>\n".format(f["table_name"])
                    # t += "<td>{}</td>\n".format(get_table(d[f["table_name"]], f, False))
                # t += "</tr>\n\n"
            # t += "</table>\n<br>"

    # return t


def get_table(data, template, with_caption=True):
    """
    create HTML table from data provided, using template thus:

    <template> := dict("table_name": <str>, "fields": [<field>, ...], 
                "stacked_headers" : <bool> (default: False),
                "optional" : [<str>, ...])
                
    <field> := <str> | <template>
    
    This allows nested tables, by putting the template for the nested
    table in the list.

    If "stacked_headers" is True, table is created with header column 
    to the left, data to the right. Default (False) results in header row.
    
    """
    if data is None or template is None:
        return ""
        
    if not isinstance(data, list):
        data = [data]
        
    if any(x not in template for x in ["table_name", "fields",]):
        return None
        
    caption = ""
    if with_caption:
        caption = "<caption>{}</caption>\n".format(template["table_name"])
    
    thead = ""
    t = ""
    stacked_headers = template.get("stacked_headers", False)

    uri_list = []
    matched_hrefs = []

    for d in data:
        # build llnks from hrefs
        # if we see data['x'] and data['x_href'], we replace data['x'] with
        # and html anchor of the form
        # <a href="data['x_href']" target="_blank">data['x']</a>
        # e.g. 
        # data['flight_number'] = "AV001", 
        # data['flight_number_href'] = "/games/155/flights/AV001/basic"
        # => data['flight_number'] = 
        # <a href="/games/155/flights/AV001/basic" target="_blank">AV001</a>
        for key in d:
            # escape all non-URI fields
            if key + "_href" in d:
                d[key] = '<a href="{}" target="_blank">{}</a>'.format(
                    d[key + "_href"], d[key])
                if key not in uri_list:
                    uri_list.append(key)
                    matched_hrefs.append(key + "_href")
            if (isinstance(d[key], str) and not re.match(r"href", key) 
            and key not in uri_list):
                d[key] = escape(d[key]).encode('ascii', 
                    'xmlcharrefreplace').decode(encoding='UTF-8')
            if re.match(r"_href", key):
                d[key] = '<a href="{}" target="_blank">{}</a>'.format(
                    d[key], d[key])
                    
    # for standard (non-stacked) table, create single table from all data
    if not stacked_headers:
        thead = "<tr>\n"
 
        # build thead <th> cells
        for f in template["fields"]:
            if isinstance(f, str):
                # for href fields, generate output only if the href is not
                # matched to another field; 
                # e.g. game_id = 155, game_id_href = "http://..../155"
                # are matched, so we do not output game_id_href
                if re.match(r"_href", f) and f in matched_hrefs:
                    continue
                thead += "<th>{}</th>\n".format(f.replace("_", "<br />"))
            elif (isinstance(f, dict) 
            and "table_name" in f and isinstance(f["table_name"], str)
            and "fields" in f and isinstance(f["fields"], list)):
                thead += "<th>{}</th>\n".format(f["table_name"])
            else:
                return ""
        thead += "</tr>\n\n"

        t = """
<table class='simple'>
{}
<thead>
{}
</thead>\n""".format(caption, thead)            

    if not stacked_headers:
        for d in data:
            # for standard table
            t += "<tr>\n<td>"
            tds = []
            for f in template["fields"]:
                if isinstance(f, dict):
                    optional = f.get("optional", False)
                    #if optional:
                    #    print("{} is optional".format(f["table_name"]))
                    if (f["table_name"] not in d
                    or (optional and len(d[f["table_name"]]) == 0)):
                        tds.append("&nbsp;")
                    else:
                        tds.append(get_table(d[f["table_name"]], f, False))
                else:
                    # for href fields, generate output only if the href is not
                    # matched to another field; 
                    # e.g. game_id = 155, game_id_href = "http://..../155"
                    # are matched, so we do not output game_id_href
                    if re.match(r"_href", f) and f in matched_hrefs:
                        continue
                    # puts blank space for missing fields
                    tds.append(format(d.get(f, "&nbsp;")))
            t += "</td>\n<td>".join(tds)
            t += "</tr>\n\n"
        t += "</table>\n\n"
    else:
        for d in data:
            t += "<table class='simple'>"
            for f in template["fields"]:
                t += "<tr>"
                if isinstance(f, str):
                    t += "<th>{}</th>".format(f)
                    t += "<td>{}</td>".format(d[f])
                elif (isinstance(f, dict) # f is a template
                and "table_name" in f and isinstance(f["table_name"], str)
                and "fields" in f and isinstance(f["fields"], list)):
                    t += "<th>{}</th>".format(f["table_name"])
                    t += "<td>{}</td>".format(get_table(d[f["table_name"]], f, False))
                t += "</tr>\n\n"
            t += "</table>"

    return t
    
def get_html(data, template):
    if data is None or template is None:
        return None
        
    html = """<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" 
xml:lang="en" lang="en" dir="ltr">

<head>
<title>AWS</title>
<style>
.simple {
    font-family: Courier, monospace, sans-serif;
    border-collapse: collapse;
}

caption {
    display: table-caption;
    text-align: center;
	font-size: 1.5em;
	font-weight: bold;
	font-variant: small-caps;
}

td {
    font-size: 1em;
    border: 1px solid #00007A;
    text-align: center;
    padding: 3px 6px;
}

th {
    font-size: 1.1em;
    text-align: center;
    padding: 3px 6px 2px 6px;
    border: 1px solid #ffffff;
    background-color: #404056;
    color: #ffffff;
}
</style>
</head>

<body>\n"""

    for t in template:
        if not isinstance(t, dict) or "table_name" not in t:
            raise Exception("Bad template {}".format(t))
        
        if t["table_name"] not in data:
            raise Exception("Bad data: missing {}\n{}".format(t["table_name"], data))

        html += get_table(data[t["table_name"]], t)
        html += "\n\n<br />\n<br>"

    html += """
</body>
</html>"""
    
    return html
    
    
template = [{ "table_name" : "country", "fields" : [ "name", "capital", { "table_name" : "leader", "fields" : [ "name", "age" ] }, "population", "area",
{ "table_name" : "mountain", "fields" : [ "name", "height" ], "optional" : True } ] }]

#template = [{ "table_name" : "country", "fields" : [ "name", "capital", { "table_name" : "leader", "fields" : [ "name", "age" ] }, "population", "area" ], "stacked_headers" : True},
#{ "table_name" : "mountain", "fields" : [ "name", "height" ] }]

data = {"country" : [{ "name" : "UK", "capital" : "London", "leader" : [{ "name" : "Queen Elizabeth II", "age" : 89}, { "name" : "David Cameron", "age" : 46 }], "population" : 65000000, "area" : 243610 , "mountain" : { "name" : "Ben Nevis", "height" : 1290} }] }
#data = {"country" : [{ "name" : "UK", "capital" : "London", "leader" : { "name" : "Queen Elizabeth II", "age" : 89}, "population" : 65000000, "area" : 243610 }]}
#print(json.dumps(data))
#,
#{ "name" : "France", "capital" : "Paris", "leader" : { "name" : "Francois Hollande", "age" : 56 }, "population" : 62000000, "area" : 304610 },
#{ "name" : "Zimbabwe", "capital" : "Harare", "leader" : { "name" : "Robert Mugabe", "age" : 91 }, "population" : 23500000, "area" : 143610 }] }

#print(get_html(data, template))