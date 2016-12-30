<?php

header('Content-Type: application/json');
header('Cache-Control: no-cache');
header('Content-Encoding: none;');

require("conf.php");
$link = getdblinki();

if (!isset($_GET['game_id']) || !is_numeric($_GET['game_id']))
{
	DebugPrint("Bad data:\n" . print_r($_GET, true));
	
	echo "{}";
}
else
{
	$sql =	"SELECT flight_id " .
			"FROM flights " .
			"WHERE game_id = {$_GET['game_id']} ".
			"AND deleted = 'N'";
	$res = mysqli_query($link, $sql);
	$flight_id_list = str_replace(array('["', '"]'), array('', ''), json_encode(mysqli_fetch_all($res)));

	// Free result set
	mysqli_free_result($res);
	
	echo $flight_id_list;
}

exit(0);
?>