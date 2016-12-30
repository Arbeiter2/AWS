<?php
// timetable/conflicts/conflicts.php

require("../../conf.php");

$debug = false;

$link = getdblinki();
mysqli_set_charset($link, 'utf8');

if (!$link)
{
	DebugPrint("TOP: bad link: " . mysqli_error());
}

header('Content-Type: application/json');
$POST = json_decode(file_get_contents("php://input"), true);
//DebugPrint(print_r($POST));

if (isset($POST['action']))
{
	switch($POST['action'])
	{
		case 'game_options': 
			getFormOptions();
			break;
		
		case 'timetables':
			getTimetableData();
			break;
			
		case 'conflicts':
			getConflicts();
			break;
			
		case 'get_timetabled_flight_list':
			getTimetabledFlightList();
			break;
		
		case 'get_flight_details':
			getTimetabledFlightData();
			break;
			
		case 'get_available_flights':
			getAvailableFlightData();
			break;
			
		default:
			DebugPrint("Bad data: ". print_r($POST, true));
			echo "{ }";
			exit;
	};
}
else
{
	DebugPrint("Bad data: ". print_r($POST, true));
	
	echo "{ }";
	exit;
}

function MinutesToHHMM($minutes)
{
	return sprintf("%02d:%02d", $minutes/60, $minutes % 60);
}

function HHMMtoMinutes($hhmm)
{
	$q = explode(':', $hhmm);
	return ($q[0] * 60) + $q[1];
}

function MinutesToHH24MM($minutes)
{
	return sprintf("%02d:%02d", ($minutes/60) % 24, $minutes % 60);
}

/* returns options for game_id and base_airport_iata
*/
function getFormOptions()
{
	global $link;

	$games = array();
	$bases = array();
	$timetables = array();
	
	$g= array();
	
	$game_options = "<option value='' empty='true'>---------------</option>\n";
	$base_options = "<option value='' empty='true'>---------------</option>\n";

	$sql =<<<EOD
SELECT DISTINCT g.game_id, g.name as game_name, airport_name, city, base_airport_iata, 
TIME_FORMAT(c.start, '%H:%i') AS curfew_start,
TIME_FORMAT(c.finish, '%H:%i') AS curfew_finish
FROM games g, flights f, routes r, airports a LEFT JOIN airport_curfews c
ON a.icao_code = c.icao_code
WHERE g.game_id = f.game_id
AND f.route_id = r.route_id
AND f.game_id = r.game_id
AND f.deleted = 'N'
AND g.deleted = 'N'
AND a.iata_code = r.base_airport_iata
ORDER BY g.name, base_airport_iata
EOD;
	$res = mysqli_query($link, $sql);
	while ($row = mysqli_fetch_array($res, MYSQL_ASSOC))
	{
		if (!isset($g[$row['game_id']]))
		{
			$game_options .= "<option value='" . $row['game_id'] . "'>" . $row['game_name'] . "</option>\n";
			$g[$row['game_id']] = $row['game_name'];
			array_push($games, array("game_id" => $row['game_id'], "name" => $row['game_name']));
		}


		if (!isset($games[$row['game_id']][$row['base_airport_iata']]))
		{
			$base_options .= "<option game_id='" . $row['game_id'] . "' value='" . $row['base_airport_iata'] . "'>" . ($row['city'] == $row['airport_name'] ? $row['city'] : $row['city'] . " - " . $row['airport_name']) . 
			" (" . $row['base_airport_iata'] . ")</option>\n";
			$base_data = array();
			$base_data['game_id'] = $row['game_id'];
			$base_data['base_airport_iata'] = $row['base_airport_iata'];
			//$base_data['city'] = utf8_encode($row['city']);
			$base_data['city'] = $row['city'];
			$base_data['airport_name'] = $row['airport_name'];
			//$base_data['airport_name'] = utf8_encode($row['airport_name']);
			if ($row['curfew_start'])
			{
				$base_data['curfew_start'] = $row['curfew_start'];
				$base_data['curfew_finish'] = $row['curfew_finish'];
			}
			$base_data['option_text'] = ($row['city'] == $row['airport_name'] ? $row['city'] : $row['city'] . " - " . $row['airport_name']) . " (" . $row['base_airport_iata'] . ")";
			
			array_push($bases, $base_data);
		}
	}

	$output = array();
	$output['game_id'] = $game_options;
	$output['bases'] = utf8_encode($base_options);
	
	$output['games_json'] = $games;	
	$output['bases_json'] = $bases;

	echo json_encode($output);
}

function fleetTypeCmp($a, $b)
{
	return strcmp($a['description'], $b['description']);
}

/*
returns data for existing flights, including
	- destination city, airport name, iata_code, timezone delta, distance, curfew hours (if any)
	- flight number, fleet_type, sector and turnaround lengths

also includes timetable summary data
*/
function getAvailableFlightData()
{
	global $link;
	//$debug = true;
	
	if (!isset($POST['game_id']) || !isset($POST['base_airport_iata']))
	{
		DebugPrint("Bad POST: " . print_r($POST, true));
		echo "{ }";
	}
	
	if (!$link)
	{
		DebugPrint("bad link: " . mysqli_error());
	}

	$fleet_types = array();
	$flights = array();

	$null_entry = array();
	$null_entry['empty'] = 'true';
	$null_entry['option_text'] = "------------";
	
	// add the special maintenance entry
	$mtx_entry = array();
	$mtx_entry['dest_airport_iata'] = 'MTX';
	$mtx_entry['class'] ='mtx'; 
	$mtx_entry['empty'] = 'true';
	$mtx_entry['distance_nm'] = 0;
	$mtx_entry['flight_number'] ="MTX";
	$mtx_entry['turnaround_length'] = "05:00";
	$mtx_entry['outbound_length'] = "00:00";
	$mtx_entry['inbound_length'] = "00:00";
	$mtx_entry['delta_tz'] = "0";
	$mtx_entry['option_text'] = "Maintenance";

	array_push($flights, $mtx_entry);
	array_push($flights, $null_entry);
	
	$fl = array();
	
	$sql = <<<EOD
SELECT distinct f.game_id,
f.flight_number,
ft.icao_code as fleet_icao_code,
f.fleet_type_id,
t.description AS fleet_type,
t.description AS fleet_type,
r.dest_airport_iata,
aa.city AS dest_city,
aa.airport_name AS dest_airport_name,
r.distance_nm,
TIME_FORMAT(f.outbound_length, '%H:%i') AS outbound_length,
TIME_FORMAT(f.inbound_length, '%H:%i') AS inbound_length,
TIME_FORMAT(f.turnaround_length, '%H:%i') AS turnaround_length,
TIME_FORMAT(ft.turnaround_length, '%H:%i') AS min_turnaround,
TIME_FORMAT(ft.ops_turnaround_length, '%H:%i') AS ops_turnaround,
TIME_FORMAT(c.start, '%H:%i') AS curfew_start,
TIME_FORMAT(c.finish, '%H:%i') AS curfew_finish,
(aa.timezone - a.timezone) AS delta_tz 
FROM flights f, routes r, fleet_types t, airports a, fleet_types ft, games g, 
airports aa LEFT JOIN airport_curfews c
ON aa.icao_code = c.icao_code
WHERE ((f.route_id = r.route_id)
AND (f.game_id = g.game_id)
AND (f.game_id = '{$POST['game_id']}')
AND (r.base_airport_iata = '{$POST['base_airport_iata']}')
AND (f.turnaround_length is not null)
AND (t.fleet_type_id = f.fleet_type_id)
AND (a.iata_code = r.base_airport_iata)
AND (aa.iata_code = r.dest_airport_iata)
AND (f.deleted = 'N')
AND (g.deleted = 'N')
AND (ft.fleet_type_id = f.fleet_type_id))
ORDER BY dest_city, dest_airport_name, flight_number
EOD;
if ($debug) DebugPrint($sql);
	$result = mysqli_query($link, $sql);
	while ($row = mysqli_fetch_array($result, MYSQL_ASSOC))
	{
		if (!isset($fl[$row['fleet_type_id']]))
		{
			$fleet_type_data = array();
			$fleet_type_data['fleet_type_id'] = $row['fleet_type_id'];
			$fleet_type_data['game_id'] = $POST['game_id'];
			$fleet_type_data['base_airport_iata'] = $POST['base_airport_iata'];
			$fleet_type_data['description'] = $row['fleet_type'];
			$fleet_type_data['min_turnaround'] = $row['min_turnaround'];
			$fleet_type_data['ops_turnaround'] = $row['ops_turnaround'];
			$fleet_type_data['fleet_icao_code'] = $row['fleet_icao_code'];

			array_push($fleet_types, $fleet_type_data);
			$fl[$row['fleet_type_id']] = 1;
		}
		usort($fleet_types, 'fleetTypeCmp');
		
		$flight_data = array();
		$flight_data['flight_number'] = $row['flight_number'];
		$flight_data['game_id'] = $POST['game_id'];
		$flight_data['base_airport_iata'] = $POST['base_airport_iata'];
		$flight_data['dest_airport_iata'] = $row['dest_airport_iata'];
		$flight_data['fleet_type_id'] = $row['fleet_type_id'];
		$flight_data['outbound_length'] = $row['outbound_length'];
		$flight_data['inbound_length'] = $row['inbound_length'];
		$flight_data['turnaround_length'] = $row['turnaround_length'];
		$flight_data['distance_nm'] = $row['distance_nm'];
		$flight_data['delta_tz'] = $row['delta_tz'];		
		//$flight_data['option_text'] = utf8_encode(($row['dest_city'] == $row['dest_airport_name'] ? $row['dest_city'] : $row['dest_city'] . " - " . $row['dest_airport_name']) . " (" . $row['dest_airport_iata'] . ") - " . $row['distance_nm'] . " nm");
		#$flight_data['option_text'] = ($row['dest_city'] == $row['dest_airport_name'] ? $row['dest_city'] : $row['dest_city'] . " - " . $row['dest_airport_name']) . " (" . $row['dest_airport_iata'] . ") - " . $row['distance_nm'] . " nm";
		
		$airport_name = $row['dest_city'];
		if ($row['dest_city'] != $row['dest_airport_name'])
		{
			if (strpos($row['dest_airport_name'], $row['dest_city']) !== FALSE)
				$airport_name = $row['dest_airport_name'];
			else
				$airport_name .= " - " . $row['dest_airport_name'];
		}
		$flight_data['option_text'] =  "$airport_name (" . $row['dest_airport_iata'] . ") - (" . $row['flight_number'] . ") - " . $row['distance_nm'] . " nm";
		if ($row['curfew_start'])
		{
			$flight_data['curfew_start'] = $row['curfew_start'];
			$flight_data['curfew_finish'] = $row['curfew_finish'];
		}		
		array_push($flights, $flight_data);
	}

	// timetable data
	$timetables = array();
	$sql =<<<EOD
SELECT game_id, timetable_id, timetable_name, base_airport_iata, fleet_type_id
FROM timetables 
WHERE deleted = 'N'
AND game_id = '{$POST['game_id']}'
AND base_airport_iata = '{$POST['base_airport_iata']}'
ORDER BY timetable_name
EOD;
	$res = 	$res = mysqli_query($link, $sql);
	while ($row = mysqli_fetch_array($res, MYSQL_ASSOC))
	{
		array_push($timetables, $row);
	}
	
	$output = array();
	$output['fleet_types'] = $fleet_types;
	$output['flights'] = $flights;
	$output['timetables'] = $timetables;
	
	echo json_encode((object) $output);
}


/* returns raw timetable data from DB:
[ 
	{
		"game_id": "162",
		"timetable_id": "42",
		"base_airport_iata": "SCL",
		"fleet_type_id": "o8",
		"timetable_name": "CC-MAA",
		"fleet_type" : "A330/A340",
		"base_turnaround_delta": "00:45",

		"entries" :
		[
			{
				"flight_number": "QV405",
				"start": "09:10",
				"earliest": "21:45",
				"padding": "00:00",
				"dest": "LIM",
				"day": 1
			},
			
			{
				"flight_number": "QV489",
				"start": "21:15",
				"earliest": "09:10",
				"padding": "00:00",
				"dest": MAN",
				"day": 1
			},
			...
		]
	},
	
	{ ... }
]
*/
function getTimetableData()
{
	global $debug;
	global $link;
	
	
	if (!isset($POST['game_id']))
	{
		echo '{ "error": "No game_id" }';
		exit;
	}
	
	$base_clause = "";
	if (isset($POST['base_airport_iata']) && preg_match('/^[A-Z]{3}$/', $POST['base_airport_iata']))
	{
		$base_clause = " AND t.base_airport_iata = '" . $POST['base_airport_iata'] . "' ";
	}
	
	$fleet_type_clause = "";
	if (isset($POST['fleet_type_id']) && preg_match('/^\d+$/', $POST['fleet_type_id']))
	{
		$fleet_type_clause = " AND t.fleet_type_id = '" . $POST['fleet_type_id'] . "' ";
	}	
	
	$name_clause = "";
	if (isset($POST['timetable_name']) && strlen(trim($POST['timetable_name'])) > 0)
	{
		$name_clause = " AND t.timetable_name = '" . $POST['timetable_name'] . "' ";
	}

	$timetable_id_clause = "";
	if (isset($POST['timetable_id']) && trim($POST['timetable_id']) > 0)
	{
		$timetable_id_clause = " AND t.timetable_id = '" . $POST['timetable_id'] . "' ";
	}
	
	$output = array();

	$sql =<<<EOD
(SELECT DISTINCT t.timetable_id, t.timetable_name, t.fleet_type_id, t.base_turnaround_delta, 
ft.description, ft.icao_code, t.base_airport_iata, te.flight_number, te.dest_airport_iata, 
te.start_day, r.distance_nm, 
TIME_FORMAT(te.start_time, '%H:%i') AS start_time, 
TIME_FORMAT(te.earliest_available, '%H:%i') AS earliest_available, 
TIME_FORMAT(te.post_padding, '%H:%i') AS post_padding, 
TIME_FORMAT(te.dest_turnaround_padding, '%H:%i') AS dest_turnaround_padding 
FROM timetables t, timetable_entries te, fleet_types ft, routes r, flights f 
WHERE t.game_id = '{$POST['game_id']}' 
AND t.game_id = r.game_id 
AND f.game_id = r.game_id 
AND f.route_id = r.route_id 
AND f.flight_number = te.flight_number 
AND t.timetable_id = te.timetable_id 
AND t.deleted = 'N' 
AND f.deleted = 'N' 
AND ft.fleet_type_id = t.fleet_type_id 
AND f.fleet_type_id = t.fleet_type_id	
$timetable_id_clause 
$base_clause 
$fleet_type_clause
$name_clause)
UNION
(SELECT DISTINCT t.timetable_id, t.timetable_name, t.fleet_type_id, t.base_turnaround_delta, 
ft.description, ft.icao_code, t.base_airport_iata, te.flight_number, te.dest_airport_iata, te.start_day, 0, 
TIME_FORMAT(te.start_time, '%H:%i') AS start_time, 
TIME_FORMAT(te.earliest_available, '%H:%i') AS earliest_available, 
TIME_FORMAT(te.post_padding, '%H:%i') AS post_padding,
TIME_FORMAT(te.dest_turnaround_padding, '%H:%i') AS dest_turnaround_padding 
FROM timetables t, timetable_entries te, fleet_types ft
WHERE t.game_id = '{$POST['game_id']}' 
AND te.flight_number = 'MTX'
AND t.timetable_id = te.timetable_id 
AND t.deleted = 'N' 
AND ft.fleet_type_id = t.fleet_type_id 
$timetable_id_clause 
$base_clause 
$fleet_type_clause 
$name_clause)
ORDER BY base_airport_iata, timetable_name, start_day, start_time
EOD;

if ($debug) DebugPrint($sql);
			
	$res = mysqli_query($link, $sql);
	while ($row = mysqli_fetch_array($res, MYSQL_ASSOC))
	{
		$key = $row['timetable_name']."-".$row['fleet_type_id']."-".$row['base_airport_iata'];
		if (!isset($output[$key]))
		{
			$output[$key] = array();
			$output[$key]['timetable_name'] = $row['timetable_name'];
			$output[$key]['timetable_id'] = $row['timetable_id'];
			$output[$key]['base_turnaround_delta'] = $row['base_turnaround_delta'];
			$output[$key]['base_airport_iata']	= $row['base_airport_iata'];
			$output[$key]['fleet_type_id']		= $row['fleet_type_id'];
			$output[$key]['fleet_type']			= $row['icao_code'];

			$output[$key]['entries'] = array();
		}
		$data = array();
		$data['flight_number']		= $row['flight_number'];
		$data['start']		= $row['start_time'];
		$data['day']		= $row['start_day'];
		$data['earliest']	= $row['earliest_available'];
		$data['padding']	= $row['post_padding'];
		$data['dest']		= $row['dest_airport_iata'];
		$data['distance_nm']		= $row['distance_nm'];

		$data['start_time']		= $row['start_time'];
		$data['start_day']		= $row['start_day'];
		$data['earliest_available']	= $row['earliest_available'];
		$data['post_padding']	= $row['post_padding'];
		$data['dest_turnaround_padding']	= $row['dest_turnaround_padding'];
		$data['dest_airport_iata']		= $row['dest_airport_iata'];		
			
		array_push($output[$key]['entries'], $data);
	}
if ($debug)	DebugPrint(json_encode(array_values($output)));
	echo json_encode(array_values($output));
}

/* simple list of flight/destination pairs
*/
function getTimetabledFlightList()
{
	global $link;

	if (!isset($POST['game_id']))
	{
		echo "{ }";
		exit;
	}
	
	$output = array();
	
	$sql =  "SELECT te.flight_number, t.fleet_type_id, te.dest_airport_iata " .
			"FROM timetables t, timetable_entries te " .
			"WHERE t.game_id = '" . $POST['game_id'] . "' " .
			"AND t.timetable_id = te.timetable_id " .
			"AND t.deleted = 'N' " .
			"AND te.flight_number <> 'MTX'";

	$res = mysqli_query($link, $sql);
	while ($row = mysqli_fetch_array($res, MYSQL_ASSOC))
	{
		array_push($output, $row);
	}
	ksort($output);
	echo json_encode($output);
}

/* returns complete flight data (includes inbound/outbound departure and arrival times) of timetabled flights indexed by base
[
	{
		"SAN" : // base 1
		[
			{
				"LAX" : // dest 1
				[
					{
						"timetable_name" : "N92203",
						"fleet_type" : "A318/A319/A320/A321",
						"flight_number" : "QV1029",
						"outbound_dep_time" : "06:45",
						"outbound_arr_time" : "07:45",
						"inbound_dep_time" : "08:55",
						"inbound_arr_time" : "10:00",
					},
					...
				]
			},
			...
			{
				"DFW" : // dest N
				[
					...
				]
			}
		]
	},

	{
		"PHX" : // base 2
		[
		...
		]
	}
]
*/
function getTimetabledFlightData()
{
	global $link;

	if (!isset($POST['game_id']) || !isset($POST['base_airport_iata']))
	{
		echo "{ }";
		exit;
	}

	$rawData = array();
	$output = array();

	$sql =  "SELECT t.timetable_name, t.base_airport_iata, t.fleet_type_id, f.description, " .
			"te.flight_number, te.dest_airport_iata, " .
			"TIME_FORMAT(te.start_time, '%H:%i') AS start_time " .
			"FROM timetables t, timetable_entries te, fleet_types f " .
			"WHERE game_id = '" . $POST['game_id'] . "' " .
			"AND base_airport_iata = '" . $POST['base_airport_iata'] . "' " .
			"AND f.fleet_type_id = t.fleet_type_id " .
			"AND t.timetable_id = te.timetable_id " .
			"AND t.deleted = 'N'";
	if ($debug) DebugPrint($sql);
	$res = mysqli_query($link, $sql);
	while ($row = mysqli_fetch_array($res, MYSQL_ASSOC))
	{
		// ignore maintenance
		if ($row['dest_airport_iata'] == 'MTX')
			continue;

		if (!isset($output[$row['base_airport_iata']]))
		{
			$output[$row['base_airport_iata']] = array();
		}
		
		if (!isset($output[$row['base_airport_iata']][$row['dest_airport_iata']]))
			$output[$row['base_airport_iata']][$row['dest_airport_iata']] = array();
		
		$flights[$row['flight_number']] = array(
			'dest' => $row['dest_airport_iata'], 
			'flight_number' => $row['flight_number'], 
			'timetable_name' => $row['timetable_name'], 
			'outbound_dep_time' => $row['start_time'], 
			'fleet_type' => $row['description'],
			'fleet_type_id' => $row['fleet_type_id']
		);
	}	

	// determine all remaining times
	// now construct the arrival/departure times for the destinations with more than one flight
	$sql = "SELECT DISTINCT f.flight_number, r.base_airport_iata, r.dest_airport_iata, TIME_FORMAT(f.outbound_length, '%H:%i') as outbound_length, TIME_FORMAT(f.inbound_length, '%H:%i') as inbound_length, " .
		   "TIME_FORMAT(f.turnaround_length, '%H:%i') as turnaround_length, (aa.timezone - a.timezone) AS delta_tz ".
		   "FROM flights f, routes r, airports a, airports aa " .
		   "WHERE r.route_id = f.route_id " .
		   "AND f.game_id = r.game_id " .
		   "AND f.game_id = '" . $POST['game_id'] . "' " .
		   "AND r.base_airport_iata = '" . $POST['base_airport_iata'] . "' " .
		   "AND f.flight_number in ('" . join ("', '", array_keys($flights)) . "') " .
		   "AND aa.iata_code = r.dest_airport_iata " .
		   "AND a.iata_code = r.base_airport_iata " .
		   "AND f.deleted = 'N' " .
		   "ORDER BY base_airport_iata, dest_airport_iata, flight_number";
	if ($debug) DebugPrint($sql);

    $res = mysqli_query($link, $sql);
	while ($row = mysqli_fetch_array($res, MYSQL_ASSOC))
	{
		$flights[$row['flight_number']]['outbound_arr_time'] = MinutesToHH24MM(HHMMtoMinutes($flights[$row['flight_number']]['outbound_dep_time']) + HHMMtoMinutes($row['outbound_length']) + ($row['delta_tz'] * 60));
		$flights[$row['flight_number']]['inbound_dep_time'] = MinutesToHH24MM(HHMMtoMinutes($flights[$row['flight_number']]['outbound_arr_time']) + HHMMtoMinutes($row['turnaround_length']));
		$flights[$row['flight_number']]['inbound_arr_time'] = MinutesToHH24MM(HHMMtoMinutes($flights[$row['flight_number']]['inbound_dep_time']) + HHMMtoMinutes($row['inbound_length']) - ($row['delta_tz'] * 60));

		array_push($output[$row['base_airport_iata']][$row['dest_airport_iata']], $flights[$row['flight_number']]);
	}
	if ($debug) DebugPrint(json_encode($output));
	echo json_encode($output);
}


/*
	getConflicts
	
	returns an array of objects containing pairs of flights with conflicting 
	departure times, either inbound or outbound; they are grouped by destination
	with details of each problematic pair
	
	{
		"SJU":
		[
			{
				"event": "inbound_dep_time",
				"dest": "DFW",
				"flights": ["QV203", "QV902"],
				"times": ["10:50", "11:05"],
				"timetable_name": ["B737-02", "B767-03"]
			},
			...
		],
		
		"LAX":
		[
		...
		],
		....
	}
	
	Optionally, the threshold (in minutes) for reporting a conflict can be specified in $POST[minimum_gap]; 
	the default value is 60
	
*/
function getConflicts()
{
	global $link;

	if (!isset($POST['game_id']) || !isset($POST['base_airport_iata']) || !isset($POST['timetable_id']) || !is_array($POST['timetable_id']))
	{
		DebugPrint("Bad 'conflicts' POST values: " . print_r($POST, true));
		echo "{ }";
		exit;
	}

	$flight_data = array();

	$sql =  "SELECT t.timetable_name, t.fleet_type_id, f.description, " .
			"te.flight_number, te.dest_airport_iata, " .
			"TIME_FORMAT(te.start_time, '%H:%i') AS start_time " .
			"FROM timetables t, timetable_entries te, fleet_types f " .
			"WHERE game_id = '" . $POST['game_id'] . "' " .
			"AND base_airport_iata = '" . $POST['base_airport_iata'] . "' " .
			"AND f.fleet_type_id = t.fleet_type_id " .
			"AND t.timetable_id = te.timetable_id " .
			"AND t.deleted = 'N' " .
			"AND te.timetable_id IN ('" . join("', '",  $POST['timetable_id']) . "')";
	$res = mysqli_query($link, $sql);
	while ($row = mysqli_fetch_array($res, MYSQL_ASSOC))
	{
		$f = array();
		
		if ($row['dest_airport_iata'] == 'MTX')
			continue;
		
		$f['flight_number'] = $row['flight_number'];
		$f['fleet_type'] = $row['fleet_type'];
		$f['timetable_name'] = $row['timetable_name'];
		$f['start'] = $row['start_time'];
		
		if (!isset($flight_data[$row['dest_airport_iata']]))
		{
			$flight_data[$row['dest_airport_iata']]= array();
		}
		$flight_data[$row['dest_airport_iata']][$row['flight_number']] = $f;
	}
	
	$multiples = array();
	$m = array();

	// find all destinations with more than one flight
	foreach (array_keys($flight_data) as $dest)
	{
		if (count($flight_data[$dest]) > 1)
		{		
			$multiples[$dest] = array();

			foreach ($flight_data[$dest] as $q)
			{
				$multiples[$dest][$q['flight_number']] = array();
				$multiples[$dest][$q['flight_number']]['fleet_type'] = $q['fleet_type'];
				$multiples[$dest][$q['flight_number']]['timetable_name'] = $q['timetable_name'];

				$multiples[$dest][$q['flight_number']]['outbound_dep_time'] = $flight_data[$dest][$q['flight_number']]['start'];
				array_push($m, $q['flight_number']);
			}
		}
	}
	
	if (!count($m))
	{
		echo json_encode($multiples);
		exit;
	}
	
	// now construct the arrival/departure times for the destinations with more than one flight
	$sql = "SELECT DISTINCT f.flight_number, r.dest_airport_iata, TIME_FORMAT(f.outbound_length, '%H:%i') as outbound_length, " .
		   "TIME_FORMAT(f.turnaround_length, '%H:%i') as turnaround_length, 
		   (aa.timezone - a.timezone) AS delta_tz ".
		   "FROM flights f, routes r, airports a, airports aa " .
		   "WHERE r.route_id = f.route_id " .
		   "AND f.game_id = r.game_id " .
		   "AND f.game_id = '" . $POST['game_id'] . "' " .
		   "AND f.flight_number in ('" . join ("', '", $m) . "') " .
		   "AND f.deleted = 'N' " .
		   "AND a.iata_code = '" . $POST['base_airport_iata'] . "' " .
		   "AND aa.iata_code = r.dest_airport_iata " .
		   "ORDER BY dest_airport_iata";
	$res = mysqli_query($link, $sql);
	while ($row = mysqli_fetch_array($res, MYSQL_ASSOC))
	{
		$x = MinutesToHH24MM(HHMMtoMinutes($multiples[$row['dest_airport_iata']][$row['flight_number']]['outbound_dep_time']) + HHMMtoMinutes($row['outbound_length']) + ($row['delta_tz'] * 60));
		$multiples[$row['dest_airport_iata']][$row['flight_number']]['inbound_dep_time'] = MinutesToHH24MM(HHMMtoMinutes($x) + HHMMtoMinutes($row['turnaround_length']));
	}
	
	$output = array();
	
	// threshold below which flights are considered in conflict;
	// for busy routes this can be as low as 30 minutes, but has a default
	// of 60 minutes; we diregard gaps >= 120
	$minimum_gap = 60;
	if (isset($POST['minimum_gap']) && $POST['minimum_gap'] > 30 && $POST['minimum_gap'] < 120)
		$minimum_gap = $POST['minimum_gap'];
	
	// process all pairs of flights in multiples to find gaps of less than 1 hour
	$fields = array('outbound_dep_time', 'inbound_dep_time');
	foreach ($multiples as $dest => $f)
	{
		for ($i=0; $i < count($f) - 1; $i++)
		{
			$flight_numbers = array_keys($f);
			for ($j=$i+1; $j < count($f); $j++)
			{				
				foreach ($fields as $time)
				{
					// if the difference between the two times exceeds 12 hours, 
					// we subtract it from 24 hours
					$diff = abs(HHMMtoMinutes($f[$flight_numbers[$i]][$time]) - HHMMtoMinutes($f[$flight_numbers[$j]][$time]));
					if ($diff > 720) // 12 hours
					{
						$diff = 1440 - $diff; 
					}
					
					if ($diff < $minimum_gap)
					{
						if (!isset($output[$dest])) 
							$output[$dest] = array();
						
						$a = array();
						$a['event'] = $time; // inbound_dep_time/outbound_dep_time
						$a['flights'] = array($flight_numbers[$i], $flight_numbers[$j]); 
						$a['times'] = array($f[$flight_numbers[$i]][$time], $f[$flight_numbers[$j]][$time]);
						$a['timetable_name'] = array($f[$flight_numbers[$i]]['timetable_name'], $f[$flight_numbers[$j]]['timetable_name']);

						array_push($output[$dest], $a);
					}
						
				}
			}
		}
	}
	ksort($output);
	echo json_encode($output);
}
?>