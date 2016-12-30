#!/usr/bin/python3

from TimetableBuilder import TimetableBuilder
import pdb
import os
import sys, getopt


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
    "Usage: {} [-g/game-id=] <game-id>\n"
      "\t\t[-b/--base=] <base-iata-code>\n"
      "\t\t[-f/--fleet-type=] <icao fleet code> ({})\n"
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


if __name__ == '__main__':    
    try:
        opts, args = getopt.getopt(sys.argv[1:], 
            "hg:b:f:s:t:m:c:d:rwiNQMj:x:G",
            ["game-id=","base=", "fleet-type=", "start-time=", "threshold=", 
            "max-range=", "count=", "turnaround-delta=", "rebuild", "write",
            "no-shuffle", "no-queue", "exclude=", "no-graveyard", "json"])
    except getopt.GetoptError as err:
        print(err)  
        usage()
        sys.exit(2)

    game_id = base = fleet_type_id = None
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

    
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-g", "--game-id"):
            game_id = a
        elif o in ("-b", "--base"):
            base = a.upper()
        elif o in ("-f", "--fleet-type"):
            fleet_type_id = types.get(a.upper(), None)
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
                sys.exit(1)
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
                sys.exit(1)
        elif o in ("-N", "--no-shuffle"):
            shuffle = False
        elif o in ("-Q", "--no-queue"):
            use_rejected = False
        elif o in ("-i", "--ignore"):
            ignore_base_timetables = False
        elif o in ("-x", "--exclude"):
            exclude = a.split(",")
        elif o in ("-M", "--mtx-gap"):
            add_mtx_gap = True
        elif o in ("-G", "--no-graveyard"):
            graveyard = False
        else:
            assert False, "unhandled option"

    print(game_id, base, fleet_type_id, start_time, threshold, 
        base_turnaround_delta, max_range, rebuild_all, writeToDatabase)
    
    if not game_id or not base or not fleet_type_id:
        usage()
        sys.exit()
        
    builder = TimetableBuilder(game_id, shuffle=shuffle, use_rejected=use_rejected)
    
    try:
        builder(base_airport_iata=base, fleet_type_id=fleet_type_id, 
            start_time=start_time, threshold=threshold, count=count,
            base_turnaround_delta=base_turnaround_delta, rebuild=rebuild_all,
            exclude_flights=exclude, writeToDB=writeToDatabase, 
            ignore_base_timetables=ignore_base_timetables, jsonDir=write_json,
            add_mtx_gap=add_mtx_gap, graveyard=graveyard)
    except Exception as e:
        print("Exception: "+str(e))
        