var allBases;
var allDestinations;
var allFleetTypes;
var allActiveTimetables;

function getFormOptions()
{
	var postData = '{ "action" : "game_options" }';
	$.ajax({
		type: 'POST',
		url: '/aws/timetable/conflicts/conflicts.php',
		data: postData,
		dataType: 'json'
	}).done(function (response)
	{
		console.log(JSON.stringify(response, null, 4));
		$('#game_id').append(response.game_id);
		$('#base_airport_iata').append(response.bases);
		allBases = $('#base_airport_iata').children().clone();
	});	
}

function getConflicts(e)
{
	e.preventDefault();
	
	if ($('#game_id').val() == '' || $('#base_airport_iata').val() == '')
		return;	

	var timetable_id = $( "input[name='timetable_id[]']:checked" );
	if (!timetable_id.length)
	{
		console.log("Nothing selected");
		return;
	}
	
	$("#resultView > tbody").find('tr').remove();
	
	var postData = '{ "action" : "conflicts" }';
	postData.game_id = $('#game_id').val();
	postData.base_airport_iata = $('#base_airport_iata').val();

	postData.timetable_id = [];
	$("input[id^='timetable_id_']").each(function() {
		if ($(this).is( ":checked" ))
			postData.timetable_id.push($(this).val());
	});
	postData = JSON.stringify(postData);

	//alert(JSON.stringify(postData, null, 4));
	
	$.ajax({
		type: 'POST',
		url: '/aws/timetable/conflicts/conflicts.php',
		data: postData,
		dataType: 'json'
	}).done(function (data)
	{
		var rows = "";
		if (!Object.keys(data).length)
		{
			rows = "<tr><td colspan='8'>No conflicts</td></tr>\n";
		}
		else
		{
			//alert(JSON.stringify(data, null, 4));
			
			$.each(data, function (destination, fData)
			{
				rows += "<tr>\n<td rowspan='" + Object.keys(fData).length + "'>" + destination + "</td>\n";
				//alert(destination + " " + JSON.stringify(fData, null, 4));

				$.each(fData, function (idx, flight) {
					if (idx != 0)
						rows += "<tr>\n";
					rows += "<td>" + flight.event.replace('_dep_time', '') + "</td>\n";
					rows += "<td>" + flight.timetable_name[0] + "</td>\n";
					rows += "<td>" + flight.flights[0] + "</td>\n";
					rows += "<td class='red0'>" + flight.times[0] + "</td>\n";
					rows += "<td class='red0'>" + flight.times[1] + "</td>\n";
					rows += "<td>" + flight.flights[1] + "</td>\n";
					rows += "<td>" + flight.timetable_name[1] + "</td>\n";
					rows += "</tr>\n"
				});
			});
			
		}
		$("#resultView > tbody").append(rows);
	});	
}

/*
*/
function getTimetables(e)
{
	e.preventDefault();
		
	var postData = { 'action' : 'timetables' };
	postData.game_id = $('#game_id').val();
	postData.base_airport_iata = $('#base_airport_iata').val();
	postData = JSON.stringify(postData);
	
	if ( $('#base_airport_iata').val() === "" )
		return;
	
	$.ajax({
		type: 'POST',
		url: '/aws/timetable/conflicts/conflicts.php',
		data: postData,
		dataType: 'json'
	}).done(function (data)
	{
	//console.log(JSON.stringify(data, null, 4));
	//console.log(data);
	
		$("#ttFormView > tbody").find('tr').remove();

		var rows = "";
		for (i=0; i < data.length; i++)
		{
			rows += "<tr>\n<td>";
			rows += data[i].timetable_name + "<br>\n";
			rows += "<input type='checkbox' name='timetable_id[]' id='timetable_id_" + data[i].timetable_id + "' value='" + data[i].timetable_id + "' checked></input>";
			rows += "</td>\n<td>" + data[i].fleet_type + "</td>\n";

			rows += "<td class='left'>";
			var list = [];
			$.each(data[i].entries, function (index, fData)
			{
				if (fData.flight_number != 'MTX')
					list.push(fData.flight_number + " (" + fData.dest + ")");
			});
			rows += list.join(', ');
			rows += "</td>\n</tr>\n\n";
			
		}
		$("#ttFormView > tbody").append(rows);

		$("input[id='timetable_name']").change(getConflicts);	
		
	});
}

function changeGame(e)
{
	$("#base_airport_iata").children().remove(); // clear children
	allBases.filter('[empty="true"]').appendTo($("#base_airport_iata"));

	if ($("#game_id").val() == "")
	{
	}
	else
	{
		allBases.filter('[game_id="' + $("#game_id").val() + '"]').appendTo($("#base_airport_iata"));
	}
}



$(document).ready(function ()
{
	getFormOptions();
	
	$("#game_id").change(changeGame);

	$("#base_airport_iata").click(getTimetables);
	$("#refresh").click(getConflicts);

});