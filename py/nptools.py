from nptime import nptime
from datetime import timedelta

def nptime_diff_sec(a, b):
    if not isinstance(a, nptime) or not isinstance(b, nptime):
        return None
        
    diff = abs((a - b).seconds)
    if diff > 43200:
        return 86400 - diff
    else:
        return diff

def str_to_timedelta(hhmmss):
    """converts string of format HH:MM:SS to timedelta object, excluding seconds"""
    if isinstance(hhmmss, timedelta):
        return hhmmss

    if not hhmmss:
        return None
    
    try:
        hh,mm = hhmmss.split(":")[0:2]
        return timedelta(hours=int(hh), minutes=int(mm))
    except ValueError:
        return None

def str_to_nptime(hhmmss):
    """converts string of format HH:MM:SS to nptime object, excluding seconds"""
    if isinstance(hhmmss, nptime):
        return hhmmss

    if not hhmmss:
        return None
    
    try:
        hh,mm = hhmmss.split(":")[0:2]
        return nptime(hour=int(hh), minute=int(mm))    
    except ValueError:
        return None

def time_to_str(obj):
    if isinstance(obj, nptime):
        obj = obj.to_timedelta()
    
    return timedelta_to_hhmm(obj)

def timedelta_to_hhmm(td):
    if not isinstance(td, timedelta):
        return ""
    else:
        total = td.total_seconds()
        return "%02d:%02d" % (total//3600, total%3600//60)

def TimeIsInWindow(t, start, finish):
    if (not isinstance(t, nptime) or not isinstance(start, nptime) 
     or not isinstance(finish, nptime)):
        raise Exception("Bad args for TimeIsInWindow")
        
    return ((start < finish and start <= t <= finish) or
            (start > finish and not (t > finish and t < start)))
