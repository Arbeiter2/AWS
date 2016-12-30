function MinutesToHHMM(minutes)
{
	return sprintf("%02d:%02d", minutes/60, minutes % 60);
}

function HHMMtoMinutes(hhmm)
{
	if (typeof hhmm === 'undefined' || hhmm == "" || hhmm == null)
		return 0;
		
	var q = hhmm.split(':');
	return parseInt(q[1]) + parseInt(q[0] * 60);
}

function MinutesToHH24MM(minutes)
{
	return sprintf("%02d:%02d", (minutes/60) % 24, minutes % 60);
}

function escapeHtml(unsafe) {
    return $('<div />').text(unsafe).html()
}

function unescapeHtml(safe) {
    return $('<div />').html(safe).text();
}

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

var allBases;
var allDestinations;
var allFlights;


function getFormOptions()
{
	var postData = { 'action' : 'game_options' };
	$.ajax({
		type: 'POST',
		url: '/aws/timetable/conflicts/conflicts.php',
		data: postData,
		dataType: 'json'
	}).done(function (data)
	{
//console.log("data = \n"+JSON.stringify(data, null, 4));
		
		$('#game_id').append(data.game_id);
		var b = $('<select></select>').html(data.bases);

		allBases = b.children().clone();
		allBases.clone().appendTo($("#base_airport_iata"));	
		//$("#base_airport_iata").children('[empty!="true"]').remove();
		
	//console.log("allbases[1] = \n"+JSON.stringify(allBases[1].text));
	});	
}

function changeGame(e)
{
	e.preventDefault();
	
	$("#base_airport_iata").children('[empty!="true"]').remove();
	allBases.clone().filter('[game_id="' + $("#game_id").val() + '"]').appendTo($("#base_airport_iata"));	
	
}


function changeBase(e)
{
	if ($("#game_id").val() == "" || $("#base_airport_iata").val() == "")
		return;
	getFlightData();

}


function changeDest(e)
{
	var dest =  $("#dest_airport_iata").val();

	$("#ttFormView > tbody").find('tr').slice(0).remove();
	$.each(allFlights, function(idx)
	{
	if ($(this).data('dest') === dest)
		$("#ttFormView > tbody").append($(this));
	});
    sorttable.makeSortable($("#ttFormView")[0]);

}

function getFlightData()
{
	allFlights = null;
	allDestinations = {};
	
	var destText= "<option empty='true'>--------</option>\n";
	var baseText = "";
	var flightText = "";
	
	if ($('#game_id').val() == '')
		return;
	game_id = $('#game_id').val();

	var postData = { 'action' : 'get_flight_details' };
	postData.game_id = game_id;
	postData.base_airport_iata = $('#base_airport_iata').val();
	postData.dest_airport_iata = $('#dest_airport_iata').val();
	
	$("#dest_airport_iata").html(destText);

	$("#ttFormView > tbody").slice(0);
	$.ajax({
		type: 'POST',
		url: 'localhost/aws/app/v1/games/155/timetables/flights',
		data: postData,
		dataType: 'json'
	}).done(function (data)
	{
		//console.log("flightData = \n"+JSON.stringify(data, null, 4));
		//return;
		
		$.each(data, function (base, fData)
		{
			//baseText += "<option value='" + base + "'>" + base + "</option>\n";
			$.each(fData, function (idx, dest) 
			{
				destText += "<option base='" + base + "' value='" + idx + "'>" + idx + "</option>\n";
				$.each(dest, function (idx2, flight)
				{
					flightText += "<tr data-base='" + base + "' " +
									  "data-dest='" + idx + "'>\n" +
								"<td>" + base + "</td>\n" +	
								"<td>" + idx + "</td>\n" +	  
								"<td>" + flight.timetable_name + "</td>\n" +
								"<td>" + flight.fleet_type + "</td>\n" +	
								"<td>" + flight.flight_number + "</td>\n" +
								"<td>" + flight.outbound_dep_time + "</td>\n" +
								"<td>" + flight.outbound_arr_time + "</td>\n" +
								"<td>" + flight.inbound_dep_time + "</td>\n" +
								"<td>" + flight.inbound_arr_time + "</td>\n" +
								"</tr>\n\n";
				});			
			});
		});
		
		destText = destText.split("\n").sort().join("\n");
		//$("#base_airport_iata").append(baseText);
		//allBases = $("#base_airport_iata").children().clone();
		
		var d = $('<select></select>').html(destText);
		allDestinations = d.children().clone();
		console.log("first destination = "+allDestinations[0].text);

		$("#dest_airport_iata").children('[empty!="true"]').remove();
		allDestinations.clone().appendTo($("#dest_airport_iata"));
	
		$("#ttFormView > tbody").append(flightText);
		allFlights = $("#ttFormView > tbody").children().clone();
		$("#ttFormView > tbody").find('tr').slice(0).remove();
		
		//console.log(allFlights);
	});	
}



$(document).ready(function ()
{
	getFormOptions();
	//getFlightData();
	
	$("#game_id").change(changeGame);
	$("#base_airport_iata").change(changeBase);
	$("#dest_airport_iata").change(changeDest);

});
