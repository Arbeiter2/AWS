<?php

require("conf.php");
$link = getdblinki();

function tidyAircraftID($acID)
{
	return str_replace('ac_', '', $acID);
}


if (!isset($_POST['game_id']) ||
	!isset($_POST['aircraft_data']))
{
DebugPrint("Bad data:\n" . print_r($_POST, true));
	return;
}
$aircraftData = json_decode($_POST['aircraft_data'], true);

$fleetTypeArray = array();
$fleetModelArray = array();
$insertArray = array();
$flightArray = array();

DebugPrint("Good data:\n" . print_r($aircraftData, true));


foreach ($aircraftData as $data)
{
	$fleetTypeArray[$data['fleet_type_id']] = "('" . $data['fleet_type_id'] . "', '" . $data['fleet_type_description'] . "')";
	$fleetModelArray[$data['fleet_type_id']] = "('" . $data['fleet_model_id'] . "', '" . $data['fleet_type_id'] . "', '" . $data['model_description'] . "')";

	array_push($insertArray,
		  "('" . $_POST['game_id'] . "', " .
		   "'" . $data['aircraft_reg'] . "', " .
		   "'" . $data['aircraft_id'] . "', " .
		   "'" . $data['fleet_model_id'] . "', " .
		   "'" . date('Y-m-d', strtotime($data['construction_date'])) . "', " .
		   "'" . $data['base_iata_code'] . "', " .
		   "'" . $data['engines'] . "', " .
		   "'" . $data['seats_Y'] . "', " .
		   "'" . $data['seats_C'] . "', " .
		   "'" . $data['seats_F'] . "')");

	if (is_array($data['flight_id']) && count($data['flight_id']) > 0)
	{
		$sql = "UPDATE flights " .
			   "SET aircraft_reg = '" . $data['aircraft_reg'] . "' " .
			   "WHERE game_id = " . $_POST['game_id'] . " " .
			   "AND flight_id in (" . implode(", ", $data['flight_id']) . ")";
		//DebugPrint($sql);
		mysqli_query($link, $sql);	
	}
}

$sql = "INSERT INTO aircraft " .
	   "(game_id, aircraft_reg, aircraft_id, fleet_model_id, construction_date, base_iata_code, engines, seats_Y, seats_C, seats_F) " .
	   "VALUES " .
implode(", ", $insertArray) .
"ON DUPLICATE KEY UPDATE " .
"aircraft_id = values(aircraft_id), " .
"fleet_model_id = values(fleet_model_id), " .
"construction_date = values(construction_date), " .
"aircraft_reg = values(aircraft_reg), " .
"base_iata_code = values(base_iata_code), " .
"engines = values(engines), " .
"seats_Y = values(seats_Y), " .
"seats_C = values(seats_C), " .
"seats_F = values(seats_F)";
//DebugPrint($sql);
mysqli_query($link, $sql);

$sql = "INSERT IGNORE INTO fleet_types (fleet_type_id, description) VALUES " . implode(", ", array_values($fleetTypeArray));
mysqli_query($link, $sql);

$sql = "INSERT IGNORE INTO fleet_models (fleet_model_id, fleet_type_id, description) VALUES " . implode(", ", array_values($fleetModelArray));
DebugPrint($sql);

mysqli_query($link, $sql);


// now tidy up deleted aircraft
$allAircraftIDs = array_map("tidyAircraftID", array_keys($aircraftData));
$sql = "UPDATE aircraft SET deleted = 'Y' WHERE aircraft_id NOT IN (" . implode(", ", $allAircraftIDs) . ")";
//DebugPrint($sql);
mysqli_query($link,$sql);

?>
