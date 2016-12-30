<?php

require("conf.php");
$link = getdblinki();
$debug = true;

header('Content-Type: application/json');

$response = array();
$response['status'] = 'OK';

if (!isset($_POST['game_id']))
{
    if ($debug) DebugPrint("renumber.php\nBad data:\n" . print_r($_POST, true));
	$response['status'] = 'ERROR';
	$response['error'] = 'Missing [game_id]';
	
	echo json_encode($response);
	return;
}
if ($debug) DebugPrint("Better data:\n" . print_r($_POST, true));

$m1 = array();
$m2 = array();
if (!preg_match_all('/^(\w{2})\d+(,\d+)*$/', $_POST['old_flight_numbers'], $m1) ||
	!preg_match_all('/^(\w{2})\d+(,\d+)*$/', $_POST['new_flight_numbers'], $m2))
{
    if ($debug) DebugPrint("renumber.php\nBad data:\n" . print_r($_POST, true));
	$response['status'] = 'ERROR';
	$response['error'] = 'Bad syntax [old_flight_numbers] or [new_flight_numbers]';

	echo json_encode($response);
	exit(1);	
}

$airline_code = substr($_POST['old_flight_numbers'], 0, 2);
$old_flight_numbers = explode(',', substr($_POST['old_flight_numbers'], 2));
$new_flight_numbers = explode(',', substr($_POST['new_flight_numbers'], 2));

if ($debug) DebugPrint( print_r ($old_flight_numbers, true) );
if ($debug) DebugPrint( print_r ($new_flight_numbers, true) );	

if (count(old_flight_numbers) != count(new_flight_numbers) ||
	count(old_flight_numbers) == 0 ||
	count(new_flight_numbers) == 0)
{
	$response['status'] = 'ERROR';
	$response['error'] = 'Flight number lists incomplete';

	echo json_encode($response);
	exit(1);
}
$response['rows_affected']['flights'] = $response['rows_affected']['timetables'] = $response['rows_affected']['flight_sectors'] = 0;

$link->autocommit(false);
for ($i=0; $i < count($old_flight_numbers); $i++)
{
	$sql = "UPDATE flights " .
		   "SET flight_number = '" . $airline_code . $new_flight_numbers[$i] . "', " .
		   "number = " . $new_flight_numbers[$i] . " " .
		   "WHERE game_id = " . $_POST['game_id'] . " " .
		   "AND deleted = 'N' " .
		   "AND flight_number = '" . $airline_code . $old_flight_numbers[$i] . "'";
	if ($debug) DebugPrint($sql);
    mysqli_query($link, $sql);
	
	$response['rows_affected']['flights'] += mysqli_affected_rows($link);
	
	// old way -- will be deprecated soon
	$sql = "UPDATE timetables " .
		   "SET entries_json = REPLACE(entries_json, '\"" . $airline_code . $old_flight_numbers[$i] . "\"', '\"" . $airline_code . $new_flight_numbers[$i] . "\"') " .
		   "WHERE game_id = " . $_POST['game_id'] . " " .
		   "AND entries_json LIKE '%\"" . $airline_code . $old_flight_numbers[$i] . "\"%'";
	if ($debug) DebugPrint($sql);
	mysqli_query($link, $sql);

	// new way
	$sql = "UPDATE timetable_entries, timetables " .
		   "SET flight_number = '" . $airline_code . $new_flight_numbers[$i] . "' " .
		   "WHERE timetables.game_id = '" . $_POST['game_id'] . "' " .
		   "AND timetable_entries.timetable_id = timetables.timetable_id " .
		   "AND timetable_entries.flight_number = '" . $airline_code . $old_flight_numbers[$i] . "'";
	if ($debug) DebugPrint($sql);
	mysqli_query($link, $sql);
	$response['rows_affected']['timetables'] += mysqli_affected_rows($link);
	
	// change flight_sectors
	/*
	$sql = "UPDATE flight_sectors " .
	"SET flight_number = '" . $airline_code . $new_flight_numbers[$i] . "' " .
	"WHERE game_id = '" . $_POST['game_id'] . "' " .
	"AND flight_number = '" . $airline_code . $old_flight_numbers[$i] . "'";
	if ($debug) DebugPrint($sql);
	mysqli_query($link, $sql);
	*/
	$response['rows_affected']['flight_sectors'] += mysqli_affected_rows($link);
	
}
$link->commit();

echo json_encode($response, JSON_NUMERIC_CHECK);
exit(0);
?>