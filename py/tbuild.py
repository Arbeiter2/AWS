#!/usr/bin/python3

from TimetableBuilder import TimetableBuilder
import pdb
import os
import sys, getopt
from datasources import RESTDataSource, DBDataSource
from flights import FlightManager
from timetables import TimetableManager
from gatimetable import GATimetable

types = {
    'F50' : 37, 
    'B732' : 22, 
    'B733' : 23, 
    'B736' : 24, 
    'A340' : 8, 
    'B757' : 28, 
    'B767' : 29, 
    'B777' : 30,
    'DH8D' : 106,
    'A320' : 7,
    }      

   
def usage():
    print(
    "Usage: {}\n"
    "\nMandatory:\n"
      "\t\t[-g/game-id=] <game-id>\n"
      "\t\t[-b/--base=] <base-iata-code>\n"
      "\t\t[-f/--fleet-type=] <icao fleet code> ({})\n"
      
    "Data source - database\n"
      "\t\t[-H/--db-host=] <database-hostname>\n"
      "\t\t[-D/--db-name=] <database-name>\n"
      "\t\t[-U/--db-user=] <database-username>\n"
      "\t\t[-P/--db-pass=] <database-password>\n"
      
    "\nData source - REST\n"
      "\t\t[-u/--uri=] <URL-stub>\n"

    "\nMode\n"
      "\t\t[-B/--build-mode=] [append | genetic]\n"

    "\nOptional\n"
      "\t\t[-s/--start-time] <HH:MM>\n"
      "\t\t[-t/--threshold=] <0.0000-0.9999>\n"
      "\t\t[-m/-max-range=] <max range allowed>\n"
      "\t\t[-c/--count=] no. of timetables to create (default=1), 0 for max\n"
      "\t\t[-d/--turnaround_delta=] <HH:MM> add to min.turnaround at base\n"
      "\t\t[-r/--rebuild] rebuild all timetables at base\n"
      "\t\t[-j/--json=] <json dir> write JSON output\n"      
      "\t\t[-w/--write] write to database\n"
      "\t\t[-N/--no-shuffle] use lexical order for flight selection\n"
      "\t\t[-Q/--no-queue] don't use reject queue\n"
      "\t\t[-x/--exclude=] [<flight-number>[,<flight-number>]]\n"
      "\t\t[-i/--ignore] ignore timetables at this base\n"
      "\t\t[-G/--no-graveyard] no flights between 00:00 and 05:00\n"
      "\t\t[-M/--mtx-gap] add turnaround gap after MTX".format(
        sys.argv[0],
        "|".join(sorted(list(types.keys()))),
        ));

    sys.exit(1)

if __name__ == '__main__':    
    try:
        opts, args = getopt.getopt(sys.argv[1:], 
            "hg:b:f:s:t:m:c:d:rwiNQMj:x:GH:D:U:P:u:B:",
            ["game-id=","base=", "fleet-type=", "start-time=", "threshold=", 
            "max-range=", "count=", "turnaround-delta=", "rebuild", "write",
            "no-shuffle", "no-queue", "exclude=", "no-graveyard", "json",
            "db-host=", "db-name=", "db-user=", "db-pass=", "uri=", 
            "build-mode="])
    except getopt.GetoptError as err:
        print(err)  
        usage()
        

    game_id = base_airport_iata = fleet_type_id = None
    db_host = db_name = db_user = db_pass = uri = None
    start_time = None
    base_turnaround_delta = None
    threshold = 0.99
    max_range = None
    count = 1
    rebuild_all = False
    writeToDatabase = False
    shuffle = True
    use_rejected = True
    exclude = None
    graveyard = True
    ignore_base_timetables = False
    add_mtx_gap = False
    write_json= None
    build_mode = "append"

    
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-H", "--db-host="):
            db_host = a
        elif o in ("-D", "--db-name="):
            db_name = a
        elif o in ("-U", "--db-user="):
            db_user = a
        elif o in ("-P", "--db-pass="):
            db_pass = a
        elif o in ("-u", "--uri="):
            uri = a
        elif o in ("-g", "--game-id"):
            game_id = a
        elif o in ("-b", "--base"):
            base_airport_iata = a.upper()
        elif o in ("-f", "--fleet-type"):
            fleet_type_id = types.get(a.upper(), None)
        elif o in ("-B", "--build-mode"):
            if a == "append" or a == "genetic":
                build_mode = a
            else:
                usage()
        elif o in ("-s", "--start-time"):
            start_time = a
        elif o in ("-d", "--turnaround-delta"):
            base_turnaround_delta = a
        elif o in ("-t", "--threshold"):
            threshold = float(a)
        elif o in ("-m", "--max-range="):
            max_range = int(a)
            if max_range <= 0:
                usage()
        elif o in ("-c", "--count="):
            count = int(a)
            if count < 0:
                usage()
                sys.exit(1)
        elif o in ("-r", "--rebuild"):
            rebuild_all = True
        elif o in ("-w", "--write"):
            writeToDatabase = True
        elif o in ("-j", "--json"):
            if os.access(a, os.W_OK):         
                write_json = a
            else:
                print("Bad dir "+a)
                usage()
        elif o in ("-N", "--no-shuffle"):
            shuffle = False
        elif o in ("-Q", "--no-queue"):
            use_rejected = False
        elif o in ("-i", "--ignore"):
            ignore_base_timetables = True
        elif o in ("-x", "--exclude"):
            exclude = a.split(",")
        elif o in ("-M", "--mtx-gap"):
            add_mtx_gap = True
        elif o in ("-G", "--no-graveyard"):
            graveyard = False
        else:
            assert False, "unhandled option"
            
    if not game_id or not base_airport_iata or not fleet_type_id:
        usage()
        
    source = None
    if (db_host and db_name and db_user and db_pass):
        source = DBDataSource(game_id, db_host=db_host, db_name=db_name, 
                              db_user=db_user, db_pass=db_pass)
    elif (uri):
        source = RESTDataSource(game_id, uri)
    else:
        raise Exception("No valid data sources provided")

    #print(game_id, base, fleet_type_id, start_time, threshold, 
    #    base_turnaround_delta, max_range, rebuild_all, writeToDatabase)

    flightMgr = FlightManager(source)
    timetableMgr = TimetableManager(source, flightMgr)
    
    if build_mode == "append":
        builder = TimetableBuilder(flightMgr, timetableMgr, shuffle=shuffle, 
                                   use_rejected=use_rejected)
        
        builder(base_airport_iata=base_airport_iata, 
                fleet_type_id=fleet_type_id, 
                start_time=start_time, threshold=threshold, count=count,
                base_turnaround_delta=base_turnaround_delta, 
                rebuild=rebuild_all, exclude_flights=exclude, 
                writeToDB=writeToDatabase, jsonDir=write_json,
                ignore_base_timetables=ignore_base_timetables, 
                add_mtx_gap=add_mtx_gap, graveyard=graveyard)
    
    elif build_mode == "genetic":
        builder = GATimetable(timetableMgr, flightMgr)
        
        builder.run(base_airport_iata, fleet_type_id, outbound_dep=start_time,
                    base_turnaround_delta=base_turnaround_delta,
                    graveyard=graveyard, ignore_existing=True)