<?php
/*
aws_commands.php
*/

require("conf.php");
$link = getdblink();


$json = file_get_contents($AWSCommandConfigFile);
if ($json === FALSE)
{
	echo ("Failed to open command JSON file");
}
else
{
	$commands = json_decode($json, true);
	if ($commands == null)
	{
		switch (json_last_error()) {
			case JSON_ERROR_NONE:
				echo ' - No errors';
			break;
			case JSON_ERROR_DEPTH:
				echo ' - Maximum stack depth exceeded';
			break;
			case JSON_ERROR_STATE_MISMATCH:
				echo ' - Underflow or the modes mismatch';
			break;
			case JSON_ERROR_CTRL_CHAR:
				echo ' - Unexpected control character found';
			break;
			case JSON_ERROR_SYNTAX:
				echo ' - Syntax error, malformed JSON';
			break;
			case JSON_ERROR_UTF8:
				echo ' - Malformed UTF-8 characters, possibly incorrectly encoded';
			break;
			default:
            echo ' - Unknown error';
			break;
		}
		echo "\n";
		exit(1);
	}
	else
	{
	}
}

/*

$_POST = array(
'command' => 'next',
'action' => 'start',
'something' => 'nothing',
'game_id' => 150,
'from-aircraft' => 'QQ-MAT'
);
*/
//DebugPrint(print_r($_POST, true));

// verify we have received a valid command
if (!isset($_POST['command']) || !isset($commands[$_POST['command']]))
{
	echo ("ERROR: command [" . $_POST['command'] . "] not valid\n");
	exit(1);
}

if (!isset($_POST['action']) || preg_match('/^(start|stop)$/', $_POST['action']) === 0)
{
	echo ("ERROR: command action [" . $_POST['action'] . "] not valid\n");
	exit(1);
}

if (!isset($_POST['game_id']) || !is_numeric($_POST['game_id']))
{
	echo ("ERROR: invalid game number [" . $_POST['game_id'] . "]\n");
	exit(1);
}

$args = array("--game_id=" . $_POST['game_id']);

// now check whether we have all the correct arguments;
// also force all arguments to upper case
foreach ($commands[$_POST['command']]['options'] as $opt)
{
	if ($opt['isMandatory'] && !isset($_POST[$opt['name']]))
	{
		echo ("ERROR: mandatory value [" . $opt['name'] . "] not set\n");
		exit(1);
	}

	if (isset($_POST[$opt['name']]) && strlen($_POST[$opt['name']]) > 0)	// in case of options passed with no value from a form
		array_push($args, "--" . $opt['name'] . ($opt['isFlag'] ? "" : "=" . trim(strtoupper($_POST[$opt['name']]))));
}


$cmd = $AWSCommandExecutablePath . " " . $_POST['action'] . " " . $commands[$_POST['command']]['script_name'] . " --html " . implode(" ", $args);
//DebugPrint($cmd);


header('Content-Type: text/html');
//header('Content-Type: application/octet-stream');
header('Cache-Control: no-cache'); // recommended to prevent caching of event data.
header('Content-Encoding: none;');

// Turn off output buffering
ini_set('output_buffering', 'off');
// Turn off PHP output compression
ini_set('zlib.output_compression', false);
// Implicitly flush the buffer(s)
ini_set('implicit_flush', true);
ob_implicit_flush(true);
// Clear, and turn off output buffering
while (ob_get_level() > 0) {
    // Get the curent level
    $level = ob_get_level();
    // End the buffering
    ob_end_clean();
    // If the current level has not changed, abort
    if (ob_get_level() == $level) break;
}   


set_time_limit(0);

$handle = popen("$cmd", "r");

if (ob_get_level() == 0)
   ob_start();

while(!feof($handle)) {
	// jQuery rejects html-like data in .html(), so we need to escape the output, 
	// and unescape when we get to the page
    $buffer = trim(htmlspecialchars(fgets($handle)));

    echo $buffer;

    ob_flush();
    flush();
    sleep(1);
}

pclose($handle);
ob_end_flush();

?>
