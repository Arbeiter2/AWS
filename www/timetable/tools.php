<?php
// timetable/tools.php

require("../conf.php");
$link = getdblink();

$game_data =array();
$fleet_type_list = array();
$min_turnaround = array();
$airport_list = array();
$base_list = array();

$sql = <<<EOD
select distinct f.game_id,
f.flight_number,
replace(f.fleet_type_id, 'a', 'o') as fleet_type_id,
t.description AS fleet_type,
r.base_airport_iata AS base,
a.city as base_city,
a.airport_name as base_airport_name,
r.dest_airport_iata AS dest,
aa.city as dest_city,
aa.airport_name as dest_airport_name,
r.distance_nm,
TIME_FORMAT(f.outbound_length, '%H:%i') as outbound_length,
TIME_FORMAT(f.inbound_length, '%H:%i') as inbound_length,
TIME_FORMAT(f.turnaround_length, '%H:%i') as turnaround_length,
TIME_FORMAT(ft.turnaround_length, '%H:%i') as min_turnaround,
(aa.timezone - a.timezone) AS delta_tz from 
(((((flights f join routes r) join fleet_types t) join airports a) join airports aa) join fleet_types ft)
where ((f.route_id = r.route_id)
and (f.turnaround_length is not null)
and (t.fleet_type_id = concat('a',substr(f.fleet_type_id,2)))
and (a.iata_code = r.base_airport_iata)
and (aa.iata_code = r.dest_airport_iata)
and (f.deleted <> 'Y')
and (ft.fleet_type_id = concat('a',substr(f.fleet_type_id,2))))
ORDER BY game_id, fleet_type
EOD;
//DebugPrint($sql);
$res = 	$res = mysql_query($sql);
while ($row = mysql_fetch_array($res, MYSQL_ASSOC))
{
	if (!isset($game_data[$row['game_id']]))
	{
		$game_data[$row['game_id']] = array();	// array of bases (bases)
	}
		
	if (!isset($game_data[$row['game_id']][$row['base']]))
	{
		$game_data[$row['game_id']][$row['base']] = array();	// array of fleet_types
	}

	if (!isset($game_data[$row['game_id']][$row['base']][$row['fleet_type_id']]))
		$game_data[$row['game_id']][$row['base']][$row['fleet_type_id']] = array();	// array of destinations

	$game_data[$row['game_id']][$row['base']][$row['fleet_type_id']][$row['flight_number']] = $row;

	// build handy lookups
	$base_list[$row['game_id']][$row['base']] = ($row['base_city'] == $row['base_airport_name'] ? $row['base_city'] : $row['base_city'] . " - " . $row['base_airport_name']) . " (" . $row['base'] . ")";
	$airport_list[$row['game_id']][$row['base']][$row['dest']] = ($row['dest_city'] == $row['dest_airport_name'] ? $row['dest_city'] : $row['dest_city'] . " - " . $row['dest_airport_name']) . " (" . $row['dest'] . ") - " . $row['distance_nm'] . " nm";
	$fleet_type_list[$row['game_id']][$row['fleet_type_id']] = $row['fleet_type'];
	$min_turnaround[$row['fleet_type_id']] = $row['min_turnaround'];
}

// base airports/bases
$base_select_options = "<option value='' empty='true'>---------------</option>\n";
$fleet_type_select_options = "<option value='' empty='true'>---------------</option>\n";
$destination_select_options =<<<EOD
<option value='' empty='true'>&nbsp;</option>
<option value='MTX' class='mtx' empty='true' distance_nm="0" flight_number="MTX" turnaround_length="05:00" outbound_length="00:00" inbound_length="00:00" delta_tz="0">Maintenance</option>
<option value='' empty='true'>---------------</option>
EOD;

$destination_select_array = array();
foreach ($game_data as $game_id => $bases)
{
	foreach ($bases as $base => $fleets)
	{
		$base_select_options .= "<option value='$base' game_id='$game_id'>" . $base_list[$game_id][$base] . "</option>\n";
		foreach ($fleets as $fleet_type_id => $destinations)
		{
			$fleet_type_select_options .= "<option value='$fleet_type_id' base_airport_iata='$base' game_id='$game_id' min_turnaround='" . $min_turnaround[$fleet_type_id] . "'>" . $fleet_type_list[$game_id][$fleet_type_id] . "</option>\n";
			foreach ($destinations as $flight_number => $data)
			{
				$key = "value='" . $data['dest'] . "' flight_number='". $flight_number . "' title='". $flight_number . "'";
				$key .= "fleet_type_id='$fleet_type_id' base_airport_iata='$base' game_id='$game_id' ";
				$key .= "distance_nm='" . $data['distance_nm'] . "' turnaround_length='" . $data['turnaround_length'] . "' outbound_length='" . $data['outbound_length'] . "' inbound_length='" . $data['inbound_length'] . "' delta_tz='" . $data['delta_tz'] . "'";
				$destination_select_array["<option $key>"] = $airport_list[$game_id][$base][$data['dest']];
			}
		}
	}
}
//DebugPrint(print_r($base_select_options, true));
// sort city names
asort($destination_select_array);
foreach ($destination_select_array as $ugly => $city)
{
	$destination_select_options .= $ugly . $city . "</option>\n";
} 


$active_timetables_options = "<option value='' empty='true'>---------------</option>\n";
$sql =<<<EOD
SELECT t.game_id, timetable_name, base_airport_iata, t.fleet_type_id, m.description 
FROM timetables t LEFT JOIN fleet_models m 
ON t.fleet_model_id = m.fleet_model_id
WHERE t.deleted = 'N'
ORDER BY game_id, timetable_name
EOD;
$res = 	$res = mysql_query($sql);
while ($row = mysql_fetch_array($res, MYSQL_ASSOC))
{
	$active_timetables_options .= 
	"<option " .
	"value='" . $row['timetable_name'] . "' " .
	"game_id='" . $row['game_id'] . "' " .
	"base_airport_iata='" . $row['base_airport_iata'] . "' " .
	"fleet_type_id='" . str_replace('a', 'o', $row['fleet_type_id']) . "'>" . 
	$row['timetable_name'] . ($row['description'] ? " (" .  $row['description'] . ")" : "") . 
	"</option>\n";
}

$output = array();
$output['base_select_options'] = utf8_encode($base_select_options);
$output['fleet_type_select_options'] = utf8_encode($fleet_type_select_options);
$output['destination_select_options'] = utf8_encode($destination_select_options);
$output['active_timetables_options'] = utf8_encode($active_timetables_options);



echo json_encode($output);

?>