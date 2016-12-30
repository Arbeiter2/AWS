<?php

require("conf.php");
$link = getdblink();

if (!isset($_POST['game_id']) ||
	!isset($_POST['distance_nm']) ||
	!isset($_POST['origin_airport_IATA']) ||
	!isset($_POST['dest_airport_IATA']))
{
//DebugPrint("Bad data:\n" . print_r($_POST, true));
	return;
}
#DebugPrint("Better data:\n" . print_r($_POST, true));



$sql = "SELECT DISTINCT route_id " .
	   "FROM routes " .
	   "WHERE game_id = " . $_POST['game_id'] . " " .
	   "AND origin_airport_IATA = '" . $_POST['origin_airport_IATA'] . "' " .
	   "AND dest_airport_IATA = '". $_POST['dest_airport_IATA'] . "'";
//DebugPrint("route check:\n".$sql);
$res = mysql_query($sql);
$row = mysql_fetch_array($res, MYSQL_ASSOC);
$route_id = $row['route_id'];
//DebugPrint("Got result" . print_r($row, true));

if (!is_numeric($route_id))
{
	$sql =  "INSERT INTO routes (game_id, origin_airport_IATA, dest_airport_IATA, distance_nm) " .
			"VALUES (" .
			"'" . $_POST['game_id'] . "', " .
			"'" . $_POST['origin_airport_IATA'] . "', " .
			"'" . $_POST['dest_airport_IATA'] . "', " .
			"'" . $_POST['distance_nm'] . "')";
//DebugPrint($sql);
	mysql_query($sql);

	// grab the new id
	$route_id = mysql_insert_id();
}

$sql =  "INSERT INTO flights (game_id, instance, flight_id, route_id, flight_number, fleet_type_id, " .
		"aircraft_type, aircraft_reg, outbound_dep_time, outbound_arr_time, " .
		"outbound_length, inbound_dept_time, inbound_arr_time, " .
		"inbound_length, days_flown) VALUES (" .
		"'" . $_POST['game_id'] . "', " .
		"'" . $_POST['instance'] . "', " .
		"'" . $_POST['flight_id'] . "', " .
		$route_id . ", " .
		"'" . $_POST['flight_number'] . "', " .
		"'" . $_POST['fleet_type_id'] . "', " .
		"'" . $_POST['aircraft_type'] . "', " .
		"'" . $_POST['aircraft_reg'] . "', " .
		"'" . $_POST['outbound_dep_time'] . "', " .
		"'" . $_POST['outbound_arr_time'] . "', " .
		"'" . $_POST['outbound_length'] . "', " .
		"'" . $_POST['inbound_dep_time'] . "', " .
		"'" . $_POST['inbound_arr_time'] . "', " .
		"'" . $_POST['inbound_length'] . "', " .
		$_POST['days_flown'] . ") ";

//DebugPrint($sql);

mysql_query($sql);
$flight_id = mysql_insert_id();

?>
