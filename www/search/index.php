<?php

// search/index.php

require("../conf.php");
$link = getdblink();

// fleet types - based on contents of flights table
$fleet_type_options = "<option value=''>--------</option>\n"; 
$sql = "SELECT DISTINCT t.fleet_type_id, description " .
	   "FROM flights f, fleet_types t " .
	   "WHERE CONCAT('a', SUBSTRING(f.fleet_type_id FROM 2)) = t.fleet_type_id ORDER BY 2";
//DebugPrint($sql);
$res = 	$res = mysql_query($sql);
while ($row = mysql_fetch_array($res, MYSQL_ASSOC))
{
$fleet_type_options .= "<option value='" . $row['fleet_type_id'] . "'>" . $row['description'] . "</option>\n";
}


?>
<!DOCTYPE html>
<html lang="en-US">
<head>
<title>AWS search</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0" />

<link rel='styleSheet' href='../style.css' type="text/css" media='screen' />

<script src="http://ajax.googleapis.com/ajax/libs/jquery/1.11.1/jquery.min.js"></script>
<script src="/aws/sorttable.js"></script> 

<style type="text/css">
/* Sortable tables */
table.sortable thead {
    background-color: #333;
    color: #cccccc;
    font-weight: bold;
    cursor: default;
}
th {
  font-size: 100%;
}
</style> 


<script>
function escapeHtml(unsafe) {
    return $('<div />').text(unsafe).html()
}

function unescapeHtml(safe) {
    return $('<div />').html(safe).text();
}
</script>

</head>

<body>

<div class='form'>
<form method="post" id='minoton'>
<table>
<tr>
<td>
	<label for="game-number" id="game-number-label">Game</label>
	<select id="game-number" name="game-number" title="AWS Game. This is a required field">
		<option value="150">Fly to the Future</option>
		<option value="157" disabled>157</option>
	</select>
</td>
</tr>

<tr>
<td>
	<label for="base" id="base-label">Base</label>
	<input id="base" name="base" type="text">
</td>
</tr>


<tr>
<td>
	<label for="destination" id="destination-label">Destination</label>
	<input id="destination" name="destination" type="text">
</td>
</tr>

<tr>
<td>
	<label for="fleet_type_id" id="fleet_type_id-label">Fleet Type</label>
	<select id='fleet_type_id' name='fleet_type_id'>
	<?=$fleet_type_options?>
	</select>
</td>
</tr>


<tr>
<td>
	<label for="flight_number" id="flight_number-label">Flight Nr</label>
	<input id="flight_number" name="flight_number" type="text">
</td>
</tr>

<tr>
<td>
	<label for="aircraft_reg" id="aircraft_reg-label">Aircraft Reg</label>
	<input id="aircraft_reg" name="aircraft_reg" type="text">
</td>
</tr>


<tr>
<td colspan='2' style='text-align: right;'>
<button id='refreshBtn' class='blueBtn'>Refresh</button>&nbsp;
<button id='cmdBtn' class='blueBtn'>Search</button>
</td>
</tr>
</table>


</form>
</div>


<div class='viewer' id='viewer'></div> <!-- viewer -->

<script>
function searchHandler(e)
{ 
	e.preventDefault();
	if (e.currentTarget.value.trim().length >= 2);
		ajax_search(false); 
}


function refreshHandler(e)
{ 
	e.preventDefault(); 
	ajax_search(true);
}

$(document).ready(function(){ 
    //$("#viewer").slideUp(); 
    $("#cmdBtn").click(searchHandler);
	$("#refreshBtn").click(refreshHandler);
	
    $("#base").keyup(searchHandler);
	$("#destination").keyup(searchHandler);
	$("#fleet_type_id").change(searchHandler);
	$("#flight_number").keyup(searchHandler); 
	$("#aircraft_reg").keyup(searchHandler); 
});
var cmdBtn = $('#cmdBtn');
	
$.fn.serializeObject = function()
{
    var o = {};
    var a = this.serializeArray();
    $.each(a, function() {
        if (o[this.name] !== undefined) {
            if (!o[this.name].push) {
                o[this.name] = [o[this.name]];
            }
            o[this.name].push(this.value || '');
        } else {
            o[this.name] = this.value || '';
        }
    });
    return o;
};


// handlers for data fields
function ajax_search(refresh)
{
	var formData = $('#minoton').serializeObject();
	if (refresh)
		formData.refresh = true;
	
	//alert('ajax_search handler called');
    $.post(            
        "dosearch.php",
 		formData,       
		function(data)
		{
			$('#viewer').html(data);
			//alert($('#results')[0]);
			sorttable.makeSortable($('#results')[0]);
		}
	);
}

</script>
</body>
</html>
