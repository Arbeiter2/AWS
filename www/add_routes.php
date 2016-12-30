<?php

require("conf.php");
$link = getdblinki();
$debug = false;

function MinutesToHHMMSS($minutes)
{
	return sprintf("%02d:%02d:00", $minutes/60, $minutes % 60);
}

$response = array();
$response['status'] = 'OK';

if (!isset($_POST['game_id']) ||
	!isset($_POST['newFlightData']))
{
    DebugPrint("add_routes.php\nBad data:\n" . print_r($_POST, true));
	$response['status'] = 'ERROR';
	$response['error'] = 'Missing [game_id] or [newFlightData]';
	
	echo json_encode($response);
	return;
}
if ($debug) DebugPrint("Better data:\n" . print_r($_POST['newFlightData'], true));

// update existing flights where required
if (isset($_POST['deletions']))
{
	$deletions = json_decode($_POST['deletions'], true);

	if (count($deletions))
	{
		$sql = "UPDATE flights SET deleted = 'Y' " .
			   "WHERE game_id = " . $_POST['game_id'] . " " .
			   "AND deleted = 'N' " .
			   "AND flight_id IN (" . implode(", ", $deletions) . ")";
		if ($debug) DebugPrint($sql);
		mysqli_query($link, $sql);
/*		
		$sql = "UPDATE flights SET deleted = 'N' " .
			   "WHERE game_id = " . $_POST['game_id'] . " " .
			   "AND deleted = 'Y' " .
			   "AND flight_id IN (" . implode(", ", $currentFlights) . ")";
		if ($debug) DebugPrint($sql);
		mysqli_query($link, $sql);		*/
	}
}

// exit if no new flights received
$newFlights = json_decode($_POST['newFlightData'], true);
if (!count($newFlights))
{
	$response['updates'] = 0;
	echo json_encode($response);
	
	exit;
}



/* newFlightData is a hash with each entry of the following structure
/ "fl_<flight_id>" : 
	{	"flight_id" : "438873"
		"aircraft_type" : "A332"
		"aircraft_reg" : "CC-MBT"
		"base_airport_iata" : "SCL"
		"dest_airport_iata" : "VVI"
		"flight_number" : "QV417"
		"fleet_type_id" : "o8"
		"distance_nm" : 1031
		"outbound_dep_time" : "18:50"
		"outbound_arr_time" : "21:55"
		"outbound_length" : "03:05"
		"turnaround_mins" : "210"
		"min_turnaround_mins" : "90"
		"inbound_dep_time" : "00:25"
		"inbound_arr_time" : "03:30"
		"inbound_length" : "03:05"
		"days_flown" : "b'0100000'"
	},
	...
*/

//DebugPrint(print_r($newFlights, true));

// create a lookup of routes
$routeLookup = array();
$sql = "SELECT CONCAT_WS('-', base_airport_iata, dest_airport_iata) as pair, route_id " .
	   "FROM routes " .
	   "WHERE game_id = " . $_POST['game_id'];
$res = mysqli_query($link, $sql);
while ($row = mysqli_fetch_array($res, MYSQL_ASSOC))
{
	$routeLookup[$row['pair']] = $row['route_id'];
}

// create a lookup of fleet type turnaround times
$turnaround_lookup = array();
$sql = "SELECT fleet_type_id, turnaround_length " .
	   "FROM fleet_types " .
	   "ORDER BY fleet_type_id";
$res = mysqli_query($link, $sql);
while ($row = mysqli_fetch_array($res, MYSQL_ASSOC))
{
	$turnaround_lookup[$row['fleet_type_id']] = $row['turnaround_length'];
}

$InseeredFlightNumbers = array();

// process each entry
$insertArray = array();
foreach ($newFlights as $flight_id => $newFlightData)
{
	$route_id = "";

	// get the route_id and add if it doesn't exist
	if (!isset($routeLookup[$newFlightData['base_airport_iata'] . "-" . $newFlightData['dest_airport_iata']]))
	{
		$sql =  "INSERT INTO routes (game_id, base_airport_iata, dest_airport_iata, distance_nm) " .
				"VALUES (" .
				"'" . $_POST['game_id'] . "', " .
				"'" . $newFlightData['base_airport_iata'] . "', " .
				"'" . $newFlightData['dest_airport_iata'] . "', " .
				"'" . $newFlightData['distance_nm'] . "')";
		//if ($debug) DebugPrint($sql);
		mysqli_query($link, $sql);

		// grab the new id
		$routeLookup[$newFlightData['base_airport_iata'] . "-" . $newFlightData['dest_airport_iata']] = $route_id = mysqli_insert_id($link);
	}
	else
	{
		$route_id = $routeLookup[$newFlightData['base_airport_iata'] . "-" . $newFlightData['dest_airport_iata']];
		//if ($debug) DebugPrint($newFlightData['base_airport_iata'] . "-" . $newFlightData['dest_airport_iata'] . " = " . $routeLookup[$newFlightData['base_airport_iata'] . "-" . $newFlightData['dest_airport_iata']]);
	}
	
	// update the turnaround field if needed
	if ($turnaround_lookup[$newFlightData['fleet_type_id']] == "00:00:00")
	{
		$sql = "UPDATE fleet_types " .
			   "SET turnaround_length = SEC_TO_TIME(" . $newFlightData['min_turnaround_mins'] . " * 60), " .
			   "ops_turnaround = SEC_TO_TIME(" . ceil(($newFlightData['min_turnaround_mins'] * 60 * 1.7)/300) * 300 . ") " .
			   "WHERE fleet_type_id = " . $newFlightData['fleet_type_id'];
		mysqli_query($link, $sql);
		
		$turnaround_lookup[$newFlightData['fleet_type_id']] = MinutesToHHMMSS($newFlightData['min_turnaround_mins']);
	}	
	
	// change days_flown from "-2----" to "b'0100000'"
	if (!preg_match("/^b'[01]{7}'$/", $newFlightData['days_flown']))
		$days_flown = "b'" . str_replace('-', '0', preg_replace('/\d/', '1', $newFlightData['days_flown'])) . "'";
	else
		$days_flown = $newFlightData['days_flown'];

	array_push($insertArray, 
		"(" .
				"'" . $_POST['game_id'] . "', " .
				"'" . $_POST['instance'] . "', " .
				"'" . $newFlightData['flight_id'] . "', " .
				$route_id . ", " .
				"'" . $newFlightData['flight_number'] . "', " .
				"'" . $newFlightData['fleet_type_id'] . "', " .
				"'" . $newFlightData['aircraft_type'] . "', " .
				"'" . $newFlightData['aircraft_reg'] . "', " .
				"'" . $newFlightData['outbound_dep_time'] . "', " .
				"'" . $newFlightData['outbound_arr_time'] . "', " .
				"'" . $newFlightData['outbound_length'] . "', " .
				"SEC_TO_TIME(" . $newFlightData['turnaround_mins'] . " * 60), " .
				"'" . $newFlightData['inbound_dep_time'] . "', " .
				"'" . $newFlightData['inbound_arr_time'] . "', " .
				"'" . $newFlightData['inbound_length'] . "', " .
				$days_flown . ", 'N')");
	
	if (!isset($InseeredFlightNumbers[$newFlightData['flight_number']]))
		$InseeredFlightNumbers[$newFlightData['flight_number']] = 1;
}
$sql =  "INSERT INTO flights (game_id, instance, flight_id, route_id, flight_number, fleet_type_id, " .
		"aircraft_type, aircraft_reg, outbound_dep_time, outbound_arr_time, " .
		"outbound_length, turnaround_length, inbound_dep_time, inbound_arr_time, " .
		"inbound_length, days_flown, deleted) VALUES " . implode(", ", $insertArray) .
		"ON DUPLICATE KEY UPDATE " .
		"instance = values(instance), " .
		"flight_number = values(flight_number), " .
		"fleet_type_id = values(fleet_type_id), " .
		"aircraft_type = values(aircraft_type), " .
		"aircraft_reg = values(aircraft_reg), " .
		"outbound_dep_time = values(outbound_dep_time), " .
		"outbound_arr_time = values(outbound_arr_time), " .
		"outbound_length = values(outbound_length), " .
		"turnaround_length = values(turnaround_length), " .
		"inbound_dep_time = values(inbound_dep_time), " .
		"inbound_arr_time = values(inbound_arr_time), " .
		"inbound_length = values(inbound_length), " .
		"days_flown = values(days_flown), " .
		"route_id = values(route_id), " .
		"deleted = values(deleted)";

//if ($debug) DebugPrint($sql);		
mysqli_query($link, $sql);

$response['updates'] = mysqli_affected_rows( $link );
$response['flight_numbers'] = array_keys($InseeredFlightNumbers);

echo json_encode($response);

?>
