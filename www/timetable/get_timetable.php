<?php
/*
get_timetable.php

returns timetable as an object of the following format:
{
"game_id": "162",
"base_airport_iata": "SCL",
"fleet_type_id": "o8",
"timetable_name": "CC-MAA",
"base_turnaround_delta": "00:45",
"entries":
	[
           {
                "fltNum": "QV405",
                "start": "09:10",
				"day": "1",
                "earliest": "21:45",
                "padding": "00:00",
                "dest": "LIM"
            },
            
            {
                "fltNum": "QV489",
                "start": "22:15",
				"day": "1",
                "earliest": "09:10",
                "padding": "00:00",
                "dest": MAN"
            },
			...
	]
}
*/

require("../conf.php");
$link = getdblinki();

header('Content-Type: application/json');


if (!isset($_POST['game_id']) ||
	!isset($_POST['base_airport_iata']) ||
	!isset($_POST['fleet_type_id']) ||
	!isset($_POST['timetable_name']))
{
    //DebugPrint("Bad data:\n" . print_r($_POST, true));
	$result = array('error' => 'Missing game_id, base_airport_iata, fleet_type_id or timetable_name');
	echo json_encode($result);
	
	exit;
}


$sql = 
	"SELECT timetable_id, base_turnaround_delta, entries_json " .
	"FROM timetables " .
	"WHERE game_id = '" . $_POST['game_id'] . "' " .
	"AND base_airport_iata = '" . $_POST['base_airport_iata']. "' " . 
	"AND timetable_name = '" . $_POST['timetable_name'] . "' " .
	"AND fleet_type_id = '" . $_POST['fleet_type_id']. "' " .
	"AND deleted = 'N'";
$res = mysqli_query($link, $sql);
$row = mysqli_fetch_array($res, MYSQL_ASSOC);
if (!isset($row['base_turnaround_delta']))
{
    //DebugPrint("Timetable not found: " . print_r($_POST, true));
	$result = array('error' => 'Timetable not found');
	echo json_encode($result);
	
	exit;	
}
$base_turnaround_delta = $row['base_turnaround_delta'];
$timetable_id = $row['timetable_id'];

$output = array();
$output['game_id']				= $_POST['game_id'];
$output['base_airport_iata']	= $_POST['base_airport_iata'];
$output['fleet_type_id']		= $_POST['fleet_type_id'];
$output['timetable_name']			= $_POST['timetable_name'];
$output['base_turnaround_delta']= $row['base_turnaround_delta'];
$output['timetable_id']			= $row['timetable_id'];

/*
$output['entries'] = json_decode( $row['entries_json'] );
DebugPrint(print_r($output, true));

echo json_encode( (object)$output );
*/
/*
for backwards compatibility with ugly old scripts, 
we return the ugly old names, as well as the internal DB 
field names, which will replace the ugly ones in due course:

	timetable_id
	flight_number
	dest_airport_iata
	start_time
	start_day
	earliest_available
	post_padding
*/
$output['entries'] = array();

$sql =  "SELECT timetable_id, flight_number, dest_airport_iata, start_day, " .
		"TIME_FORMAT(start_time, '%H:%i') AS start_time, " .
		"TIME_FORMAT(earliest_available, '%H:%i') AS earliest_available, " .
		"TIME_FORMAT(post_padding, '%H:%i') AS post_padding " .
		"FROM timetable_entries " .
	    "WHERE timetable_id = $timetable_id " .
		"ORDER BY start_day, start_time";
$res = mysqli_query($link, $sql);
while ($row = mysqli_fetch_array($res, MYSQL_ASSOC))
{
	$data = $row;
	$data['fltNum'] = $row['flight_number'];
	$data['start'] = $row['start_time'];
	$data['day'] = $row['start_day'];
	$data['earliest'] = $row['earliest_available'];
	$data['padding'] = $row['post_padding'];
	$data['dest'] = $row['dest_airport_iata'];
	
	array_push($output['entries'], $data);
}
//DebugPrint(print_r($output, true));

echo json_encode( (object)$output );

?>
