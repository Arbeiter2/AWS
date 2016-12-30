<?php
// search/index.php
session_start();

require("../conf.php");
$link = getdblink();

function iata_lookup($val, $mode)
{
	$results = array();
	if (strlen($val) == 3)
	{
		foreach ($_SESSION['flights'] as $flight_id => $data)
		{
			if ($data[$mode.'_airport_iata'] == $val)
			{
				array_push($results, $flight_id);
			}
		}
	}
	return $results;
}

function icao_lookup($val)
{
	if (strlen($val)== 4)
	{
		foreach ($_SESSION['airports'] as $iata_code => $data)
		{
			if ($data['icao_code'] == $val)
			{
				return $iata_code;
			}
		}
	}
	return FALSE;
}


function flight_search($val, $field, $exact =true)
{
	$results = array();
	foreach ($_SESSION['flights'] as $flight_id => $data)
	{
		if (($exact && $data[$field] == $val) || (!$exact && strpos($data[$field], $val) !== FALSE))
		{
			array_push($results, $flight_id);
		}
	}
//DebugPrint(print_r($results, true));	
	return $results;
}


function initialise()
{
	$_SESSION['airports'] = array();
	$_SESSION['flights'] = array();
	$_SESSION['aircraft'] = array();

	// airport codes
	$sql = 
	"SELECT iata_code, icao_code, airport_name, city " .
	"FROM airports " .
	"ORDER BY iata_code";
	$res = mysql_query($sql);
	while ($row = mysql_fetch_array($res, MYSQL_ASSOC))
	{
		$_SESSION['airports'][$row['iata_code']] = $row;
	}

	// flights + aircraft
	$sql = 
	"SELECT r.base_airport_iata, r.dest_airport_iata, r.distance_nm, " .
	"f.flight_id, f.flight_number, f.aircraft_reg, f.aircraft_type, " .
	"f.outbound_dep_time, f.outbound_arr_time, f.outbound_length, turnaround_length, f.inbound_dep_time, f.inbound_arr_time, f.inbound_length, " .
	"ADDTIME(f.outbound_length, ADDTIME(turnaround_length, f.inbound_length)) AS rotation_time, " .
	"f.days_flown+0 as days, " .
	"CONCAT('a', SUBSTRING(f.fleet_type_id FROM 2)) AS fleet_type_id " . 
	"FROM flights f, routes r " .
	"WHERE f.game_id = 150 " .
	"AND f.route_id = r.route_id " .
	"AND deleted = 'N' " .
	"ORDER BY flight_number" ;
	DebugPrint($sql);
	$res = mysql_query($sql);
	while ($row = mysql_fetch_array($res, MYSQL_ASSOC))
	{
		$_SESSION['flights'][$row['flight_id']] = $row;
		if (strlen($row['aircraft_reg']))
		{
			if (!isset($_SESSION['aircraft'][$row['aircraft_reg']]))
			{
				$_SESSION['aircraft'][$row['aircraft_reg']] = array();
				$_SESSION['aircraft'][$row['aircraft_reg']]['type'] = $row['aircraft_type'];
				$_SESSION['aircraft'][$row['aircraft_reg']]['flights'] = array();
			}
			array_push($_SESSION['aircraft'][$row['aircraft_reg']]['flights'], $row['flight_id']);
		}
	}
}


if (!isset($_SESSION['airports']) || isset($_POST['refresh']))
{
	//DebugPrint("Refreshing tables");
	initialise();
}

//DebugPrint(print_r($_POST, true));
//DebugPrint(print_r($_SESSION['flights'], true));
$final = array_keys($_SESSION['flights']);

// base
if (isset($_POST['base']) && preg_match('/^[A-Z]{3,4}$/', strtoupper($_POST['base'])))
{
	$results = array();
	$len = strlen($_POST['base']);
	if ($len == 3) // IATA code
	{
		$results = flight_search(strtoupper($_POST['base']), 'base_airport_iata', true);
	}
	elseif ($len == 4) // ICAO code
	{
		$results = flight_search(icao_lookup(strtoupper($_POST['base'])), 'base_airport_iata', true);
	}
	$final = array_intersect($final, $results);
}
//DebugPrint("After base:\n" . print_r($final, true));


// destination
if (isset($_POST['destination']) && preg_match('/^[A-Z]{3,4}$/', strtoupper($_POST['destination'])))
{
	$results = array();
	$len = strlen($_POST['destination']);
	if ($len == 3) // IATA code
	{
		$results = flight_search(strtoupper($_POST['destination']), 'dest_airport_iata', true);
	}
	elseif ($len == 4) // ICAO code
	{
		$results = flight_search(icao_lookup(strtoupper($_POST['destination'])), 'dest_airport_iata', true);
	}
	
	//$final = (count($final) > 0 ? array_intersect($final, $results) : $results);
	$final = array_intersect($final, $results);
}
//DebugPrint("After dest:\n" . count($final));

// flight_number
if (isset($_POST['flight_number']) && preg_match('/^\w{2}[0-9]+$/', $_POST['flight_number']) == 1)
{
	// tidy the flight number
	$code = substr(strtoupper($_POST['flight_number']), 0, 2);
	$number = sprintf("%03d", substr($_POST['flight_number'], 2));
	$results = flight_search($code . $number, 'flight_number');
	//$final = (count($final) > 0 ? array_intersect($final, $results) : $results);
	$final = array_intersect($final, $results);
}
//DebugPrint("After flight_number:\n" . count($final));

// fleet_type_id
if (isset($_POST['fleet_type_id']) && preg_match('/^\w\d+$/', $_POST['fleet_type_id']))
{
	$results = flight_search($_POST['fleet_type_id'], 'fleet_type_id');
	//$final = (count($final) > 0 ? array_intersect($final, $results) : $results);
	$final = array_intersect($final, $results);
}
//DebugPrint("After fleet_type_id:\n" . count($final));

// aircraft_reg
if (isset($_POST['aircraft_reg']) && strlen($_POST['aircraft_reg']) > 4)
{
	$results = array();
	if (isset($_SESSION['aircraft'][strtoupper($_POST['aircraft_reg'])]))
		$results = $_SESSION['aircraft'][strtoupper($_POST['aircraft_reg'])]['flights'];
	//$final = (count($final) > 0 ? array_intersect($final, $results) : $results);
	$final = array_intersect($final, $results);
}
//DebugPrint("After aircraft_reg:\n" . print_r($final, true));

$output = <<<EOD
<table id='results' name='results' class='CSSTableGenerator sortable'>
<thead>
<tr>
<td>Flight Nr</td>
<td>Orig</td>
<td>Dest</td>
<td>Dist<br />nm</td>
<td>Type</td>
<td>Aircraft<br />Reg</td>
<td>Outbound<br /><img src='/aws/img/airplane_takeoff.png' height='16px' width='16px' />&nbsp;dep</td>
<td>Outbound<br /><img src='/aws/img/airplane_landing.png' height='16px' width='16px' />&nbsp;arr</td>
<td>Outbound<br />length</td>
<td>Inbound<br /><img src='/aws/img/airplane_takeoff.png' height='16px' width='16px' />&nbsp;dep</td>
<td>Inbound<br /><img src='/aws/img/airplane_landing.png' height='16px' width='16px' />&nbsp;arr</td>
<td>Inbound<br />length</td>
<td>Rotation<br />Time</td>
<td>Days</td>
</tr>
</thead>

<tbody>
EOD;

if (!count($final))
{
	$output .= "<tr><td colspan='14'>No flights found</td></tr>\n";
}
else
{
	foreach ($final as $flight_id)
	{
	// days flown as 1234567 form
	$d = "";
	for ($s=6; $s >= 0; $s--)
		$d .= ((1 << $s) & $_SESSION['flights'][$flight_id]['days'] ? (7-$s) : '-');
		
	$output .= "<tr>" . 
	"<td><a href='http://www.airwaysim.com/game/Routes/View/" . $flight_id . "/' target='_blank'>" . $_SESSION['flights'][$flight_id]['flight_number'] . "</a></td>" . 
	"<td>" . $_SESSION['flights'][$flight_id]['base_airport_iata']. "</td>" . 
	"<td>" . $_SESSION['flights'][$flight_id]['dest_airport_iata'] . "</td>" . 
	"<td>" . $_SESSION['flights'][$flight_id]['distance_nm'] . "</td>" . 
	"<td>" . $_SESSION['flights'][$flight_id]['aircraft_type'] . "</td>" . 
	"<td>" . $_SESSION['flights'][$flight_id]['aircraft_reg'] . "</td>" . 
	"<td>" . $_SESSION['flights'][$flight_id]['outbound_dep_time'] . "</td>" . 
	"<td>" . $_SESSION['flights'][$flight_id]['outbound_arr_time'] . "</td>" . 
	"<td>" . $_SESSION['flights'][$flight_id]['outbound_length'] . "</td>" . 
	"<td>" . $_SESSION['flights'][$flight_id]['inbound_dep_time'] . "</td>" . 
	"<td>" . $_SESSION['flights'][$flight_id]['inbound_arr_time'] . "</td>" . 
	"<td>" . $_SESSION['flights'][$flight_id]['inbound_length'] . "</td>" . 
	"<td>" . $_SESSION['flights'][$flight_id]['rotation_time'] . "</td>" .
	"<td>" . $d . "</td>" .
	"</tr>\n";
	}
}
$output .= "</tbody>\n</table>\n";
//DebugPrint($output);
print $output;

?>