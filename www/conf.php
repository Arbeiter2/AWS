<?php

function getdblink()
{
    $link = mysqli_connect('localhost', 'mysql', 'password');
    if (!$link)
    {
        die('Could not connect: ' . mysqli_error());
    }
    mysqli_select_db($link, 'airwaysim');
	mysqli_query('SET NAMES latin1'); 
    return $link;
}

function getdblinki()
{
    $linki = mysqli_connect('localhost', 'mysql', 'password', 'airwaysim');
    if (mysqli_connect_errno($linki))
    {
        die('Could not connect: ' . mysqli_connect_error());
    }
	mysqli_query($linki, 'SET NAMES latin1');
    return $linki;
}


function DebugPrint($s)
{
    $linki = getdblinki();
    $escaped_string = mysqli_escape_string($linki, $s);
    $qry = "INSERT INTO junk (junk_dt, data) VALUES (now(), '$escaped_string')";
    mysqli_query($linki, $qry);
}

$AWSCommandConfigFile = "./aws_commands.js";

$AWSCommandExecutablePath = "C:/js/aws.cmd";
if (strtoupper(substr(PHP_OS, 0, 3)) !== 'WIN') {
	$AWSCommandExecutablePath = "/home/delano/casperjs/aws_controller.sh";
} else {
}


?>
