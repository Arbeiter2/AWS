<?php
// timetable/conflicts/conflicts.php

require("../conf.php");
$link = getdblinki();

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


/* returns raw timetable data from DB:
[
{ 
	"CC-MAA" : 
	{
		"fleet_type" : "A330/A340",
		"entries" :
		[
			{
				"fltNum": "QV405",
				"start": "09:10",
				"earliest": "21:45",
				"padding": "00:00",
				"dest": "LIM",
				"day": 1
			},
			
			{
				"fltNum": "QV489",
				"start": "21:15",
				"earliest": "09:10",
				"padding": "00:00",
				"dest": MAN",
				"day": 1
			},
			...
		]
	},
	
	"CC-MAB" : { ... }
]
*/
{
	$flight_data = array();

	$sql =  "SELECT * " .
			"FROM timetables t " .
			"WHERE entries_json like '%\"day\"%'";
	$res = mysqli_query($link, $sql);
	while ($row = mysqli_fetch_array($res, MYSQL_ASSOC))
	{
		$fData = json_decode($row['entries_json'], true);
		foreach ($fData as $obj)
		{
			array_push($flight_data, "( " .
			$row['timetable_id'] . ", " .
			"'" . $obj['fltNum'] . "', " .
			"'" . $obj['dest'] . "', " .
			"'" . $obj['start'] . "', " .
			"'" . $obj['day'] . "', " .
			"'" . $obj['earliest'] . "', " .
			"'" . $obj['padding'] . "' " .
			")");
		}
		//echo "Added " . $row['aircraft_reg'] . "\n";
	}
}
$sql = 
"INSERT INTO timetable_entries ( timetable_id, flight_number, dest_airport_iata, start_time, start_day, earliest_available, post_padding) " .
"VALUES " . implode(", ", $flight_data);
echo "$sql\n";
//mysqli_query($link, $sql);

?>