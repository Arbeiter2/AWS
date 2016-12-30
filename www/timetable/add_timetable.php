<?php

require("../conf.php");
$link = getdblinki();

$debug = true;

header('Content-Type: application/json');

$result = array();

if (!isset($_POST['game_id']) ||
	!isset($_POST['entries']) ||
	!isset($_POST['base_airport_iata']) ||
	!isset($_POST['timetable_name']) ||
	!isset($_POST['base_turnaround_delta']))
{
	$result['status'] = 'ERROR';
	$result['text'] = 'Bad POST options';
	
	echo json_encode($result);
	exit;
}

if ($debug) DebugPrint(print_r($_POST, true));


// find the fleet_type_id for this model
if (isset($_POST['fleet_model_id']) && !isset($_POST['fleet_type_id']))
{
	$sql = "SELECT fleet_type_id FROM fleet_models WHERE fleet_model_id = '" . $_POST['fleet_model_id'] . "'";
	$res = mysqli_query($link, $sql);
	
	$row = mysqli_fetch_array($res, MYSQL_ASSOC);
	if (!$row['fleet_type_id'])
	{
		$result['status'] = 'ERROR';
		$result['text'] = 'Bad fleet_model_id [' . $_POST['fleet_model_id'] . ']';
		echo json_encode($result);
		if ($debug) DebugPrint(print_r($result, true));
		exit;
	}
	$_POST['fleet_type_id'] = $row['fleet_type_id'];
}

// verify supplied timetable_id, or find if not supplied
$timetable_id = -1;
if (isset($_POST['timetable_id']) && is_numeric($_POST['timetable_id']))
{
	$sql = 
		"SELECT count(*) as confirmed " .
		"FROM timetables " .
		"WHERE game_id = '" . $_POST['game_id'] . "' " .
		"AND timetable_id = '" . $_POST['timetable_id'] . "'";
	$res = mysqli_query($link, $sql);
	$row = mysqli_fetch_array($res, MYSQL_ASSOC);

	// bomb if invalid
	if (!$row['confirmed'])
	{
		$result['status'] = 'ERROR';
		$result['text'] = 'Bad timetable_id';
		
		echo json_encode($result);
		if ($debug) DebugPrint(print_r($result, true));
		exit;		
	}
	else
	{
		$timetable_id = $_POST['timetable_id'];
	}
}
else // look for the timetable_id from supplied details
{
	$sql = 
		"SELECT timetable_id " .
		"FROM timetables " .
		"WHERE game_id = '" . $_POST['game_id'] . "' " .
		"AND base_airport_iata = '" . $_POST['base_airport_iata'] . "' " . 
		"AND fleet_type_id = '" . $_POST['fleet_type_id'] . "' " .
		"AND timetable_name = '" . $_POST['timetable_name'] . "'";
	$res = mysqli_query($link, $sql);
	$row = mysqli_fetch_array($res, MYSQL_ASSOC);
	$timetable_id = (is_numeric($row['timetable_id']) ? $row['timetable_id'] : -1);
}


// check whether the flights are already in the database
$entries = json_decode($_POST['entries'], true);
if ($debug) DebugPrint(print_r($entries, true));

$flights = array();
foreach ($entries as $data)
{
	if ($data['flight_number'] != 'MTX')
		array_push($flights, $data['flight_number']);
}

// bomb if no entries found
if (count($flights) == 0)
{
	$result['status'] = 'ERROR';
	$result['text'] = 'No flights provided';
	echo json_encode($result);
	if ($debug) DebugPrint(print_r($result, true));

	exit;
}

$pattern = implode("', '", $flights);

$other_aircraft = array();
$sql =	"SELECT DISTINCT timetable_name, e.flight_number " .
		"FROM timetables t, timetable_entries e " .
		"WHERE t.game_id = '" . $_POST['game_id'] . "' " .
		"AND t.timetable_id = e.timetable_id " .
		"AND t.fleet_type_id = '" . $_POST['fleet_type_id'] . "' " .
		"AND t.deleted = 'N' " .
		"AND e.flight_number IN ('" . implode("', '", $flights) . "') " .
		"AND t.timetable_id <> '" . $timetable_id . "'";
if ($debug) DebugPrint($sql);
$res = mysqli_query($link, $sql);
while ($row = mysqli_fetch_array($res, MYSQL_ASSOC))
{
	if (!isset($other_aircraft[$row['timetable_name']]))
		$other_aircraft[$row['timetable_name']] = array();

	array_push($other_aircraft[$row['timetable_name']], $row['flight_number']);
}

if (count($other_aircraft))
{
	$result['status'] = 'ERROR';
	$result['text'] = "Duplicate flights:\n";
	foreach ($other_aircraft as $timetable_name => $flights)
	{
		$result['text'] .= "    $timetable_name: " . implode(", ", $flights) . "\n";
	}
	echo json_encode($result);
	if ($debug) DebugPrint(print_r($result, true));
	
	exit;
}


$sql =  "INSERT INTO timetables (game_id, timetable_id, timetable_name, fleet_model_id, fleet_type_id, base_airport_iata, base_turnaround_delta, entries_json) " .
		"VALUES (" .
		"'" . $_POST['game_id'] . "', " .
		"'" . $_POST['timetable_id'] . "', " .
		"'" . $_POST['timetable_name'] . "', " .
		"'" . $_POST['fleet_model_id'] . "', " .
		"'" . $_POST['fleet_type_id'] . "', " .
		"'" . $_POST['base_airport_iata'] . "', " .
		"'" . $_POST['base_turnaround_delta'] . "', " .
		"'" . $_POST['entries'] . "') " .
		"ON DUPLICATE KEY UPDATE " .
		"timetable_name = values(timetable_name), " .
		"entries_json = values(entries_json), " .
		"base_turnaround_delta = values(base_turnaround_delta)";
if ($debug) DebugPrint($sql);
mysqli_query($link, $sql);
/*
$err = "(" . mysqli_error($link) . ") " . mysqli_errno($link);
if ($debug) DebugPrint($err);
*/

if ($debug) DebugPrint("Added " . $_POST['timetable_name']);


// get the new timetable_id if needed
if ($timetable_id == -1)
{
	$timetable_id = mysqli_insert_id ( $link );
}

$sql = "DELETE FROM timetable_entries WHERE timetable_id = $timetable_id";
$res = mysqli_query($link, $sql);

// now some extra stuff
$sql_inserts = array();

foreach ($entries as $obj)
{
	array_push($sql_inserts, 
		"( " .
		$timetable_id . ", " .
		"'" . $obj['flight_number'] . "', " .
		"'" . $obj['dest_airport_iata'] . "', " .
		"'" . $obj['start_time'] . "', " .
		"'" . $obj['start_day'] . "', " .
		"'" . $obj['dest_turnaround_padding'] . "', " .
		"'" . $obj['earliest_available'] . "', " .
		"'" . $obj['post_padding'] . "' " .
		")");		
}
$sql = "INSERT INTO timetable_entries ( timetable_id, flight_number, dest_airport_iata, start_time, start_day, dest_turnaround_padding, earliest_available, post_padding) VALUES " . implode(", ", $sql_inserts);
if ($debug) DebugPrint($sql);
mysqli_query($link, $sql);

$result['status'] = 'OK';
$result['timetable_id'] = $timetable_id;

if ($debug) DebugPrint(json_encode($result));

echo json_encode($result);
exit;

?>
