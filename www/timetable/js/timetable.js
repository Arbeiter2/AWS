var allBases = null;
var allDestinations = null;
var allFleetTypes = null;
var allActiveTimetables = null;
var assignedFlights = [];
var airportLookup = {};

var rowTemplate;
var hasMaintenance = false;



function MinutesToHHMM(minutes)
{
	return sprintf("%02d:%02d", minutes/60, minutes % 60);
}

function HHMMtoMinutes(hhmm)
{
	if (typeof hhmm === 'undefined' || hhmm === "" || hhmm === null)
		return 0;
		
	var q = hhmm.split(':');
	return parseInt(q[1]) + parseInt(q[0] * 60);
}

function MinutesToHH24MM(minutes)
{
	if (minutes < 0)
	{
		//console.log("MinutesToHH24MM got [" + minutes + "]");
		minutes += (24 * 60);
	}
	return sprintf("%02d:%02d", (minutes/60) % 24, minutes % 60);
}

function escapeHtml(unsafe) {
    return $('<div />').text(unsafe).html();
}

function unescapeHtml(safe) {
    return $('<div />').html(safe).text();
}

function sleep(milliseconds) {
  var start = new Date().getTime();
  for (var i = 0; i < 1e7; i++) {
    if ((new Date().getTime() - start) > milliseconds){
      break;
    }
  }
}

function getIndexOfFlight(arr, flight_number, fleet_type_id)
{
	var out = -1;
	for (i=0; i < arr.length; i++)
	{
		if (arr[i].flight_number == flight_number &&  arr[i].fleet_type_id == fleet_type_id)
		{
			out = i;
			break;
		}
	}
	return out;
}

var getUrlParameter = function getUrlParameter(sParam) {
    var sPageURL = decodeURIComponent(window.location.search.substring(1)),
        sURLVariables = sPageURL.split('&'),
        sParameterName,
        i;

    for (i = 0; i < sURLVariables.length; i++) {
        sParameterName = sURLVariables[i].split('=');

        if (sParameterName[0] === sParam) {
            return sParameterName[1] === undefined ? true : sParameterName[1];
        }
    }
};

/*
	creates an array of HTMLElement option objects, using the data from the provided array of 
	JSON objects; the field called valueFieldName is set to the "value" attribute, while the
	field called titleFieldName (if specified) is set to the "title"
*/
function buildOptionList(data, textFieldName, valueFieldName, titleFieldName)
{
	if (data === undefined || !Array.isArray(data))
		return [];

	var output = [];
	output[0] = new Option("---------------", "");
	output[0].setAttribute('empty', true);
	
	for (i=0; i < data.length; i++)
	{
		opt = new Option(data[i][textFieldName], data[i][valueFieldName] );
		if (titleFieldName !== undefined) 
			opt.title = data[i][titleFieldName];
		
		// now add the remaining attributes
		for (var field in data[i])
		{
			if (field == textFieldName || field == valueFieldName || field.match(/_href$/))
				continue;
			
			opt.setAttribute(field, data[i][field]);
		}
		output.push(opt);
//		console.log(opt);
	}
	return output;
}

/*
*/
function getFormOptions(callback)
{
//	console.log("In getFormOptions())");
	
	var postData = { 'action' : 'game_options' };
	$.ajax({
		type: 'GET',
		//url: '/aws/timetable/conflicts/conflicts.php',
		//data: postData,
		url: 'http://localhost/aws/app/v1/games/bases',
		dataType: 'json'
	}).done(function (response)
	{
//		console.log(JSON.stringify(response, null, 4));
		var bsl = [];
		var gsl = [];
		for (i=0; i < response['airports'].length; i++)
		{
			game = response['airports'][i];

			gsl.push({ game_id: game.game_id, name: game.name });
			for (j=0; j < game.bases.length; j++)
			{
				base = game.bases[j];
				base.option_text = (base.city == base.airport_name ? base.city : base.city + " - " + base.airport_name) + " (" + base.iata_code + ")";
				base.game_id = game.game_id;
			}
			bsl.push.apply(bsl, game.bases);
		}
//		console.log(JSON.stringify(bsl, null, 4));
//		console.log(JSON.stringify(gsl, null, 4));
		
		var b = buildOptionList(bsl, 'option_text', 'iata_code');
		var g = buildOptionList(gsl, 'name', 'game_id');

		$('#game_id').empty();
		$('#game_id').append(g);

		//$('#base_airport_iata').empty();
		bs = $('<select></select>').append(b);
		allBases = bs.children().clone();
		
		if (callback !== undefined)
			callback();
	});	
}

function refreshHandler(e)
{ 
	e.preventDefault();
	$("#spinner").toggle();
	
	// save the values of all input elements
	var formValues = {};
	var flightsSeen = [];
	$("select").each(function (index)
	{
		// if you call .val() enough times, it returns null;
		// not cool
		//formValues[$(this)[0].id] = $(this).val();
		var e = $(this)[0];
		if (e.selectedIndex > -1)
			formValues[e.id] = document.querySelector('#' + e.id).options[e.selectedIndex].value;
		else
			formValues[e.id] = "";

		if (/^destination\d+/.test(e.id) && e.selectedIndex != -1)
		{
			flightsSeen.push(document.querySelector('#' + e.id).options[e.selectedIndex].getAttribute('flight_number'));
		}
	});

	getFormOptions(function() 
	{
		if (!formValues.game_id.match(/^\d+/) )
			return;
console.log("formValues.game_id = " +formValues.game_id);
		
		// now reset the values of the top level form
		$('#game_id').val(formValues.game_id);

		//$("#base_airport_iata").children().remove();
		$("#base_airport_iata").children('[empty!="true"]').remove();
		allBases.clone().filter('[game_id="' + $('#game_id').val() + '"]').appendTo($("#base_airport_iata"));
		$('#base_airport_iata').val(formValues.base_airport_iata);
		
		//$("#fleet_type_id").children('[empty!="true"]').remove();
		//allFleetTypes.clone().filter('[game_id="' + $('#game_id').val() + '"][base_airport_iata="' + $('#base_airport_iata').val() + '"]').appendTo($("#fleet_type_id"));
		//$('#fleet_type_id').val(formValues.fleet_type_id);
	});
	
	if (formValues.game_id === undefined || formValues.game_id === '')
	{
		$("#spinner").toggle();
		return;
	}
	
	getFleetTypes(function() {
		$("#fleet_type_id").children().remove();
		allFleetTypes.clone().filter('[empty="true"]').appendTo($("#fleet_type_id"));
		allFleetTypes.clone().filter('[game_id="' + $('#game_id').val() + '"][base_airport_iata="' + $('#base_airport_iata').val() + '"]').appendTo($("#fleet_type_id"));
		
		$("#fleet_type_id").val(formValues.fleet_type_id);
	});

	getAvailableFlightsFromBase(function() 
	{
		$("#active_timetables").children('[empty!="true"]').remove();
		allActiveTimetables.clone().filter('[game_id="' + $('#game_id').val() + '"][base_airport_iata="' + $('#base_airport_iata').val() + '"][fleet_type_id="' + $('#fleet_type_id').val() + '"]').appendTo($("#active_timetables"));
		$('#active_timetables').val(formValues.active_timetables);

		// change destination entries in situ
		for (var elementId in formValues)
		{
			if (/destination\d+/.test(elementId))
			{
				$("#" + elementId).children('[empty!="true"]').remove();

				allDestinations.clone().filter('[game_id="' + $('#game_id').val() + '"][base_airport_iata="' + $('#base_airport_iata').val() + '"][fleet_type_id="' + $('#fleet_type_id').val() + '"]').appendTo($('#' + elementId));
				$('#' + elementId).val(formValues[elementId]);
				
				//console.log('#' + elementId+" = "+formValues[elementId]);
				
				//console.log($('#' + elementId)[0]);
			}
		}	

		// first mark everything back to normal
		if (flightsSeen.length)
		{
			$('select[id^="destination"]').children().removeClass('inUse');	
			filter = flightsSeen.map(function(str) { 
				if (str !== 'MTX' && str !== '')
					return '[flight_number="' + str + '"]';
				else
					return '[flight_number="utterly impossible"]';
			}).join(",");
//console.log(filter);
		
			$('select[id^="destination"]').children(filter).addClass('inUse');
		}
		toggleUnassigned(e);
	});
	$("#spinner").toggle();

}

/*
function getAvailableFlightsFromBase(callback)
{
	var postData = { 
		action : 'get_available_flights',
		game_id : $('#game_id').val(),
		base_airport_iata : $('#base_airport_iata').val()
	};
	$.ajax({
		type: 'POST',
		url: '/aws/timetable/conflicts/conflicts.php',
		data: postData,
		dataType: 'json'
	}).done(function (flightData)
	{
//		console.log(JSON.stringify(flightData, null, 4));
		
		var fleet_types = buildOptionList(flightData.fleet_types, 'description', 'fleet_type_id');
		var fs = $('<select></select>').append(fleet_types);
		allFleetTypes = fs.children().clone();
//		console.log(allFleetTypes);
		
		var flights = buildOptionList(flightData.flights, 'option_text', 'dest_airport_iata', 'flight_number');
		var ffs = $('<select></select>').append(flights);
		allDestinations = ffs.children().clone();
//		console.log(allDestinations);

		var timetables = buildOptionList(flightData.timetables, 'timetable_name', 'timetable_id');
		var ts = $('<select></select>').append(timetables);
		allActiveTimetables = ts.children().clone();
//		console.log(allActiveTimetables);


		if (callback !== undefined)
			callback();
	});		
}
*/

function getAvailableFlightsFromBase(callback)
{
	game_id = $('#game_id').val();
	base_airport_iata = $('#base_airport_iata').val();
	if (game_id === null || base_airport_iata === null)
		return;
//console.log('http://localhost/aws/app/v1/games/' + game_id + '/flights/' + base_airport_iata)	
	$.ajax({
		type: 'GET',
		url: 'http://localhost/aws/app/v1/games/' + game_id + '/flights/' + base_airport_iata,
		dataType: 'json'
	}).done(function (flightData)
	{
//		console.log(JSON.stringify(flightData.fleet_types, null, 4));
//		console.log("fleet_types");

//		console.log(JSON.stringify(flightData, null, 4));
		
//		var fleet_types = buildOptionList(flightData.fleet_types, 'description', 'fleet_type_id');
//		var fs = $('<select></select>').append(fleet_types);
//		allFleetTypes = fs.children().clone();
//		console.log(allFleetTypes);

		for (j=0; j < flightData.flights.length; j++)
		{
			f = flightData.flights[j];
			if (f.flight_number === 'MTX')
				continue;

			airport_name = f.dest_city;
			if (f.dest_city != f.airport_name)
			{
				if (f.dest_airport_name.indexOf(f.dest_city) != -1)
					airport_name = f.dest_airport_name;
				else
					airport_name += " - " + f.dest_airport_name;
			}
			f.option_text = airport_name + " (" + f.dest_airport_iata + ") - (" + f.flight_number + ") - " + f.distance_nm + " nm";
		}		
//		console.log(JSON.stringify(flightData[0].flights, null, 4));

		var flights = buildOptionList(flightData.flights, 'option_text', 'dest_airport_iata', 'flight_number');
		var ffs = $('<select></select>').append(flights);
		allDestinations = ffs.children().clone();
//		console.log(allDestinations);


		$.ajax({
			type: 'GET',
			url: 'http://localhost/aws/app/v1/games/' + game_id + '/timetables/' + base_airport_iata,
			dataType: 'json'
		}).done(function (timetableData)
		{
//console.log(JSON.stringify(timetableData, null, 4));

			var timetables = buildOptionList(timetableData.timetables, 'timetable_name', 'timetable_id');
			var ts = $('<select></select>').append(timetables);
			allActiveTimetables = ts.children().clone();
	//		console.log(allActiveTimetables);
		});
		
		if (callback !== undefined)
			callback();
	});	
}


function formFilterHandler(e)
{
	e.preventDefault();
	switch (e.currentTarget.name)
	{
	case 'fleet_type_id':
		clearDestinations();
		clearTimetable();
		break;
		
	case 'base_airport_iata':
		getAvailableFlightsFromBase(function() {
			clearFleetTypes();
			clearTimetable();
		});
		break;
		
	case 'game_id':
		clearBases();
		clearTimetable();
		break;
	}
}


function clearDestinations()
{
	//	console.log(allDestinations);
	if (allDestinations !== null)
	{
		$('select[name^="destination"]').children().remove();
		allDestinations.clone().filter('[empty="true"]').appendTo($('select[name^="destination"]'));	
		allDestinations.clone().filter('[game_id="' + $('#game_id').val() + '"][base_airport_iata="' + $('#base_airport_iata').val() + '"][fleet_type_id="' + $('#fleet_type_id').val() + '"]').appendTo($('select[name^="destination"]'));
	}
	
	if (allActiveTimetables !== null)
	{
		$('#active_timetables').children().remove();
		allActiveTimetables.clone().filter('[empty="true"]').appendTo($('#active_timetables'));	
		
		allActiveTimetables.clone().filter('[game_id="' + $('#game_id').val() + '"][base_airport_iata="' + $('#base_airport_iata').val() + '"][fleet_type_id="' + $('#fleet_type_id').val() + '"]').appendTo($('#active_timetables'));

		$("#base_turnaround").val($('#fleet_type_id')[0].selectedOptions[0].getAttribute('ops_turnaround'));
		$("#base_turnaround").attr('min', $('#fleet_type_id')[0].selectedOptions[0].getAttribute('ops_turnaround'));
	}
}


function clearFleetTypes()
{
	$("#fleet_type_id").children().remove();
	
	if (allFleetTypes !== null)
	{
		allFleetTypes.clone().filter('[empty="true"]').appendTo($("#fleet_type_id"));
		allFleetTypes.clone().filter('[game_id="' + $('#game_id').val() + '"][base_airport_iata="' + $('#base_airport_iata').val() + '"]').appendTo($("#fleet_type_id"));
	
		$("#base_turnaround").val("00:00");
		clearDestinations();
	}
}

function clearBases()
{
	currentTimetableData = { };
	
	$("#base_airport_iata").children('[empty!="true"]').remove();
	if (allBases !== null)
		allBases.clone().filter('[game_id="' + $('#game_id').val() + '"]').appendTo($("#base_airport_iata"));

	getFleetTypes(function() {
		getAssignedFlights(function() {
			clearFleetTypes();
		});
	})
}


function clearTimetable()
{
	$("#timetable > tbody").find('tr').slice(1).remove();
	$("#active_timetables").val("");					// blank out selected timetable
	
	// set all flights to "not in use" in current timetable
	$('select[id^="destination"]').children().removeClass('inUse');

	
	// blank flight number, distance etc from first row 
	$("#destination1").val("");

	var x = [ 1, 3, 6, 8, 9, 11, 12 ];
	for (i=0; i < x.length; i++)
	{
		$("#timetable > tbody > tr:nth-child(1) > td:nth-child(" + x[i] + ")").html("");
	}

	currentTimetableData = { };

	disableAssignedFlights($('#destination1'), UnassignedFlightsOnly);
	
	$( '#destination1' ).val("");
	$( '#padding1' ).val("00:00");
	
	$( '#TimetableTotal' ).html("00:00");
	$( '#TimetableTotal' ).removeClass();

	$( '#TimetableTotal_hhmm' ).html("00:00");
	$( '#TimetableTotal_hhmm' ).removeClass();
	
	$( '#AirborneTotalTime_hhmm' ).html("00:00");
	$( '#AirborneTotalTime_pct' ).html("0.0");
	$( '#avg_daily_airborne_hrs' ).html("0.0");
	$('#restful_uri').html('');

	$('#timetable > tbody > tr > td').removeClass('yellowback');
	
	// register all handlers
	/*
	$('select[id="destination2"]').change(destinationHandler);
	$('input[id="padding2"]').change(ttEntryChange);
	$('img[id="add_dest2"]').click(addTimetableRow);
	$('img[id="delete_dest2"]').click(deleteTimetableRow);
	*/
	
}

/*
** get a list of all flights already assigned to other aircraft in saved timetables
*/

function getAssignedFlights(callback)
{
	if ($('#game_id').val() === '')
	{	
		assignedFlights = [];
		return;
	}
	/*
		//console.log("Starting getAssignedFlights");	
	var postData = {};
	postData.action = 'get_timetabled_flight_list';
	postData.game_id = $('#game_id').val();
	
	$.ajax({
		type: 'POST',
		url: '/aws/timetable/conflicts/conflicts.php',
		data: postData,
		dataType: 'json'
	}).done(function (data)
	{
		assignedFlights = data;
		if (callback !== undefined)
			callback();
		//console.log("Completed getAssignedFlights");
		//console.log(JSON.stringify(data, null, 4));
	});*/
	
	$.ajax({
		type: 'GET',
		url: 'http://localhost/aws/app/v1/games/' + $('#game_id').val() + '/timetables/flights',
		dataType: 'json'
	}).done(function (data)
	{
		assignedFlights = data.flights;
		if (callback !== undefined)
			callback();
		//console.log("Completed getAssignedFlights");
//		console.log(JSON.stringify(data, null, 4));
	});
}

function getFleetTypes(callback)
{
	if ($('#game_id').val() === '')
	{	
		allFleetTypes = null;
		return;
	}
	
	$.ajax({
		type: 'GET',
		url: 'http://localhost/aws/app/v1/games/' + $('#game_id').val() + '/fleets',
		dataType: 'json'
	}).done(function (data)
	{
//		console.log(JSON.stringify(data, null, 4));

		var fleet_types = buildOptionList(data.fleets, 'description', 'fleet_type_id');
		var fs = $('<select></select>').append(fleet_types);
		allFleetTypes = fs.children().clone();
		
//		console.log(allFleetTypes);
		
		if (callback !== undefined)
			callback();
		//console.log("Completed getAssignedFlights");
	}).fail(function( jqXHR, textStatus, errorThrown )
	{
		console.log("ERROR: " + jQuery.parseJSON(jqXHR.responseText).error);
	});
}

var UnassignedFlightsOnly = false;
/*
disable/enable all timetabled flights in the destination dropdowns
*/
function disableAssignedFlights(obj, disable)
{
	if (disable)
	{
		var targets = assignedFlights.slice(0);
		var FleetTypeID = $('#fleet_type_id').val();
//	console.log(JSON.stringify(targets, null, 4));
		
		// if we are looking at a prebuilt timetable, delete the flights it contains from the list to be unassigned
		var currentTimetable = $("#active_timetables").val();
		if (currentTimetable !== null && currentTimetable !== "" && currentTimetableData.entries !== undefined)
		{
			var i=0;
			$.each(currentTimetableData.entries, function(idx, event)
			{
				i++;
				if (event.flight_number !== "MTX")
				{
					var m = getIndexOfFlight(targets, event.flight_number, FleetTypeID);
					
//console.log("getIndexOfFlight("+event.flight_number+", "+FleetTypeID+") = "+m);
					if (m >= 0)
					{
						targets.splice(m, 1);
//console.log(i + ": Deleted " + event.flight_number);
					}
				}

			});
		}
//console.log(JSON.stringify(targets, null, 4));

		filter = targets.map(function (flight) {
			return "[flight_number='" + flight.flight_number + "']"; //[fleet_type_id='" + flight.fleet_type_id + "']";
		}).join(",");
		
//console.log(filter);
		var options = obj.find(filter);
//console.log(options);
		options.attr('disabled', 'disabled');
		/*		
		$.each(targets, function(index, flight) {
			if (flight.fleet_type_id == FleetTypeID)
			{
//console.log("Disable "+index+": "+flight.flight_number + "/"+flight.dest_airport_iata);
				var options = obj.find("option[flight_number='" + flight.flight_number + "'][value='" + flight.dest_airport_iata + "']");
//console.log(options);
				options.attr('disabled', 'disabled');
			}
		});*/
	}
	else
	{
		// we re-enable all the disabled options
//console.log("Re-enabling "+obj[0].id);		
		// TODO: repair this asap
		obj.find("option").prop('disabled', false);
		obj.find("option").removeAttr('disabled');
	}	
}

function toggleUnassigned(e)
{
	e.preventDefault();
	
	UnassignedFlightsOnly = $('#unassigned_only').is(":checked");
/*	
	alert("UnassignedFlightsOnly = "+UnassignedFlightsOnly+"; val() = "+$('#unassigned_only').val());
	
	if (UnassignedFlightsOnly)*/
		getAssignedFlights(function() {
			disableAssignedFlights($('select[id^="destination"]'), UnassignedFlightsOnly);
		});
}

function destinationHandler(e)
{
	e.preventDefault();
	
	// check whether there is more than one maintenance check
	if ($( '#' + e.currentTarget.id ).val() == 'MTX' && !checkMaintenance())
	{
		alert("Only one maintenance entry permitted!");
	}
	
	// 1-indexed location of this row
	var parentRow = $( '#' + e.currentTarget.id ).parents("tr:first");
	var index = parentRow.index() + 1;
	
	var element = e.currentTarget.selectedOptions[0];
	$('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(1)').html(element.getAttribute('flight_number'));
	$('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(3)').html(element.getAttribute('distance_nm'));
	
	ttEntryChange(e);
}

function enableLoadButton(e)
{
	e.preventDefault();
	
	if ($('#active_timetables').val() === "" || $('#active_timetables').val() === null)
	{
		$('#loadTimetable').attr('disabled', true);
	}
	else
	{
		$('#loadTimetable').removeAttr('disabled');
	}
}

//
// checks whether there is precisely one maintenance entry
//
function checkMaintenance()
{
	hasMaintenance = false;
	var maintCount = 0;
	$.each($('select[name^="destination"]'), function() 
	{
		maintCount += ($(this).val() == 'MTX' ? 1 : 0);
	});
	
	hasMaintenance = (maintCount == 1);
	
	return hasMaintenance;
}

var TimetableTotal, AirborneTotalTime;

			
// check for curfew
function isOutOfHours(optionObj, flightTime) 
{
	if (optionObj.hasAttribute('curfew_start'))
	{
		var curfewStart = optionObj.getAttribute('curfew_start');
		var curfewFinish = optionObj.getAttribute('curfew_finish');
		
		// check for pairs like 02:00 - 06:00, or 23:00 - 06:00
		if ((curfewStart < curfewFinish && flightTime > curfewStart && flightTime < curfewFinish) ||
			(curfewStart > curfewFinish && !(flightTime > curfewFinish && flightTime < curfewStart)))
		{
			return true;				
		}
	}
	return false;
}

/*
*/
function ttEntryChange(e)
{
	TimetableTotal = AirborneTotalTime = MaxDistance = 0;
	start_day = parseInt($('#start_day').val());

	//console.log("ttEntryChange type:"+e.type);
	if (!(e.type === "click" || e.type === "change" ))
	{
		//return;
	}
	else
	{
		e.preventDefault();
	}
	

	
//	if (e.currentTarget.id.match(/dest_padding/))
//		console.log("Looking at "+e.currentTarget.id);

	$('#exportCSV').attr('disabled', true);
	$('#exportJSON').attr('disabled', true);
		
	// ensure we have a valid base turnaround time 
	if ($('#base_turnaround').val().match(/^\d{2}:\d{2}/) === null || $('#base_turnaround').val() < $('#base_turnaround').attr('min'))
	{
		alert("Check base turnaround value\n" + $('#base_turnaround').val() + " < " + $('#base_turnaround').attr('min') );
		$('#base_turnaround').focus();
		//$('#exportCSV').attr('disabled', true);
		//$('#exportJSON').attr('disabled', true);
	}
	
	var flights_seen = {};
	var destination_entries = [];


	var baseData = $('#base_airport_iata')[0].selectedOptions[0];
	
	for (var index=1; index <= $("#timetable > tbody > tr").length; index++)
	{
		// we keep track of which flight numbers we have seen, and record their index locations in the table;
		// if we see the number again, we highlight all of the duplicates
		$('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(1)').removeClass('red0');
		$('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(1)').removeClass('blink');

		var flight_number = $('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(1)').text();
		if (flights_seen[flight_number] !== undefined)
		{
			// mark duplicates
			flights_seen[flight_number].push( index );
			$.each(flights_seen[flight_number], function(i, idx) {
				$('#timetable > tbody > tr:nth-child(' + idx + ') > td:nth-child(1)').addClass('red0');
				$('#timetable > tbody > tr:nth-child(' + idx + ') > td:nth-child(1)').addClass('blink');
			});
		}
		else
		{
			flights_seen[flight_number] = [ index ];
		}
		
		// grab variable index from hidden value
		var vn = $("#timetable > tbody > tr:nth-child(" + index + ") > td:nth-last-child(1) > input").attr("name").replace('total_hours', '');
		destination_entries.push(vn);

		var flightData = $('#destination' + vn)[0].selectedOptions[0];
		
		start_day_cell = $('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(4)');
		start_time_cell = $('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(5)');
		
		// copy values for available day and time to next row
		if (index == 1)
		{
			if (index != vn)
			{
				// ensure start_day selector is in row 1
				start_day_select = $('#start_day').detach();
				start_day_cell.empty();
				start_day_select.appendTo(start_day_cell);
				
				start_time_select = $('#outbound_dep_time1').detach();
				start_time_cell.empty();
				start_time_select.appendTo(start_time_cell);
			}
		}
		else
		{
			// departure day(X) = available_day(X-1)
			$('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(4)').text($('#timetable > tbody > tr:nth-child(' + (index-1) + ') > td:nth-child(12)').text());
			
			// outbound_dep_time(X) = available_time(X-1)
			$('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(5)').text($('#timetable > tbody > tr:nth-child(' + (index-1) + ') > td:nth-child(11)').text());
			
			start_day = parseInt($('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(4)').text());
		}

		if (flight_number != 'MTX')
		{
			$('#timetable > tbody > tr:nth-child(' + index + ') > td').removeClass('yellowback');
			$('#dest_padding' + vn).removeAttr('disabled');
		}
		else
		{
			// for the MTX row, set all backgrounds to yellow
			$('#timetable > tbody > tr:nth-child(' + index + ') > td').addClass('yellowback');
			
			// MTX has no dest_padding, so disable it and set to 00:00
			$('#dest_padding' + vn).val("00:00");
			$('#dest_padding' + vn).attr('disabled', true);
		}
		

		// get outbound dep time
		var depTime;
		if (index == 1)
			depTime = $('#outbound_dep_time1').val();
		else
			depTime = $('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(5)').text();
		
		outbound_arr_time = MinutesToHH24MM(HHMMtoMinutes(depTime) + 
								  HHMMtoMinutes(flightData.getAttribute('outbound_length')) + 
								  flightData.getAttribute('delta_tz') * 60);
		
//console.log("dest_padding" + vn + " = " + $('#dest_padding' + vn).val()	);
	
		inbound_dep_time = MinutesToHH24MM(HHMMtoMinutes(outbound_arr_time) + 
								  HHMMtoMinutes(flightData.getAttribute('turnaround_length')) +
								  HHMMtoMinutes($('#dest_padding' + vn).val()));

		inbound_arr_time = MinutesToHH24MM(HHMMtoMinutes(inbound_dep_time) + 
								  HHMMtoMinutes(flightData.getAttribute('inbound_length')) -
								  flightData.getAttribute('delta_tz') * 60);
								  
		available_time = MinutesToHH24MM(HHMMtoMinutes(inbound_arr_time) + 
								  (flightData.getAttribute('value') == 'MTX' ? 0 : HHMMtoMinutes($('#base_turnaround').val())) +
								  HHMMtoMinutes($('#padding' + vn).val()));
/*
		// we now add the standard turnaround after MTX entries
		available_time = MinutesToHH24MM(HHMMtoMinutes(inbound_arr_time) + 
								  (flightData.getAttribute('value') == 'MTX' ? HHMMtoMinutes($('#fleet_type_id')[0].selectedOptions[0].getAttribute('min_turnaround')) : HHMMtoMinutes($('#base_turnaround').val())) +
								  HHMMtoMinutes($('#padding' + vn).val()));
*/								  
		// outbound arrival
		$('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(6)').html(outbound_arr_time);
								  
		// inbound dep
		$('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(8)').html(inbound_dep_time);

		// inbound arr
		$('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(9)').html(inbound_arr_time);
								  
		// available time
		$('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(11)').html(available_time);					  

		// total turnaround
		$('#total_hours' + vn ).val(MinutesToHHMM(HHMMtoMinutes(flightData.getAttribute('outbound_length')) +
							   HHMMtoMinutes(flightData.getAttribute('turnaround_length')) +
							   HHMMtoMinutes($('#dest_padding' + vn).val()) +
							   HHMMtoMinutes(flightData.getAttribute('inbound_length')) +
							   (flightData.getAttribute('value') == 'MTX' ? 0 : HHMMtoMinutes($('#base_turnaround').val())) +
							   HHMMtoMinutes($('#padding' + vn).val()))
		);
		
		// available day = departure day + parseInt((outbound_dep_time1 + total turnaround)/(60 * 24))
		var newDay = start_day + 
								parseInt((HHMMtoMinutes(depTime) +		
								HHMMtoMinutes($('#total_hours' + vn).val()))/(60 * 24));
		if (newDay > 7)
			newDay = newDay % 7;
		$('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(12)').html(newDay);

		// check whether departure/arrival times are at undesirable hours
		// as well as whether they fall in curfew hours
		for (var m=5; m <= 9; m++)
		{
			var cell = $('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(' + m +')');

			cell.removeClass('red0');
			cell.removeClass('blink');
			
			cell.removeAttr('title');
		
			var flightTime = (index == 1 && m == 5 ? depTime : cell.text().trim());
			if (flightData.getAttribute('flight_number') != 'MTX' && flightTime > "00:30" && flightTime < "05:15")
			{
				cell.addClass('red0');
				//cell.addClass('blink');
			}
			
			// check for curfew violation
			// 5 + 9 are base departure and arrival
			// 6 + 8 are destination arrival and departure
			if ((m == 5 || m == 9) && isOutOfHours(baseData, flightTime) || // base airport 
				(m == 6 || m == 8) && isOutOfHours(flightData, flightTime)) // destination airport 
			{
				cell.addClass('red0');
				cell.addClass('blink');
				if (m == 5 || m == 9)
				{
					cell.attr('title', "Closed "+baseData.getAttribute('curfew_start')+"-"+baseData.getAttribute('curfew_finish'));
				}
				else
				{
					cell.attr('title', "Closed "+flightData.getAttribute('curfew_start')+"-"+flightData.getAttribute('curfew_finish'));
				}
			}				
		}

		// distance
		var distance_nm = parseInt($('#timetable > tbody > tr:nth-child(' + index + ') > td:nth-child(3)').text());
		MaxDistance = (distance_nm > MaxDistance ? distance_nm : MaxDistance);
		
		// total hours airborne
		AirborneTotalTime += HHMMtoMinutes(flightData.getAttribute('outbound_length')) + HHMMtoMinutes(flightData.getAttribute('inbound_length'));
		TimetableTotal += parseInt(HHMMtoMinutes($('#total_hours' + vn ).val()));
	}

	// renumber destination and other fields
	field_names = ['destination', /*'outbound_dep_time', */'dest_padding', 'padding', 'total_hours'];
	for (var vn=1; vn <= destination_entries.length; vn++)
	{
		for (i=0; i < field_names.length; i++)
		{
			// change to temporary names
			$('#' + field_names[i] + destination_entries[vn-1]).attr(
				{ 
					'id' : '_' + field_names[i] + vn, 
					'name' : '_' + field_names[i] + vn
				}
			);
			//console.log("vals = " + $('#' + field_names[i] + destination_entries[vn-1]).val() + ", "+$('#' + field_names[i] + vn).val());
		}
		$('#add_dest' + destination_entries[vn-1]).attr ('id', '_add_dest' + vn);
		$('#delete_dest' + destination_entries[vn-1]).attr ('id', '_delete_dest' + vn);			
	}

	for (var vn=1; vn <= destination_entries.length; vn++)
	{
		for (i=0; i < field_names.length; i++)
		{
			// change to final names
			$('#' + '_' + field_names[i] + vn).attr(
				{ 
					'id' : field_names[i] + vn, 
					'name' : field_names[i] + vn
				}
			);
		}
		$('#_add_dest' + vn).attr ('id', 'add_dest' + vn);
		$('#_delete_dest' + vn).attr ('id', 'delete_dest' + vn);			
	}
	//console.log("vals = " + $('#' + field_names[i] + destination_entries[vn-1]).val() + ", "+$('#' + field_names[i] + vn).val());
	
	
	// mark all selected flights in green
	
	// first mark everything back to normal
	$('select[id^="destination"]').children().removeClass('inUse');

	filter = Object.keys(flights_seen).map(function(str) { 
		if (str !== 'MTX' && str !== '')
			return '[flight_number="' + str + '"]';
		else
			return '[flight_number="utterly impossible"]';
	}).join(",");
	
	$('select[id^="destination"]').children(filter).addClass('inUse');


	// update summary
	$( '#TimetableTotal_hhmm' ).html(MinutesToHHMM(TimetableTotal));
	$( '#TimetableTotal_hhmm' ).removeClass();
	var ratio = TimetableTotal / (168*60);
	if (ratio > 1.0)
	{
		$( '#TimetableTotal_hhmm' ).addClass('red0');
		$( '#TimetableTotal_hhmm' ).addClass('blink');
	}
	else
	{
		if (ratio > 0.95)
			$( '#TimetableTotal_hhmm' ).addClass('green0');
		else if (ratio > 0.85)
			$( '#TimetableTotal_hhmm' ).addClass('green1');
		else if (ratio > 0.80)
			$( '#TimetableTotal_hhmm' ).addClass('green2');
	}
		
	// only enable the export buttons if ratio is correct, maintenance added, and no duplicates found 
	if (ratio <= 1.0 && 
		checkMaintenance() &&
		$('#timetable > tbody > tr > td:nth-child(1).red0.blink').length === 0)
	{
		$('#exportCSV').removeAttr('disabled');
		$('#exportJSON').removeAttr('disabled');
	}
	else
	{
		//console.log("ratio = "+ratio+", maintenance = "+hasMaintenance+", blinking = "+$('#timetable > tbody > tr > td:nth-child(1).red0.blink').length); 
	}
	
	$( '#AirborneTotalTime_hhmm' ).html(MinutesToHHMM(AirborneTotalTime));
	$( '#AirborneTotalTime_pct' ).html(sprintf("%0.1f", 100.0 * AirborneTotalTime/(168*60)));
	$( '#avg_daily_airborne_hrs' ).html(sprintf("%0.1f", AirborneTotalTime/(60 * 7)));
	$( '#max_distance_nm' ).html(MaxDistance);

}

function addTimetableRow(e)
{
	//console.log("Starting addTimetableRow()");
	e.preventDefault();

	// new index number is based on the highest value presently in the table, rather than the 
	// number of table rows
	var max_vn = -1;
	$.each($('select[id^="destination"]'), function() {
	var thisVn = parseInt($(this).attr('id').replace('destination', ''));
	if (thisVn > max_vn)
		max_vn = thisVn;
	});
	var new_vn = max_vn + 1;
	//var new_vn = $("#timetable > tbody > tr").length + 1;
	
	
	// use the rowTemplate and do search/replace
	var newHtml = rowTemplate
						.replace(/destination2/g, 'destination' + new_vn)
						.replace(/outbound_dep_time2/g, 'outbound_dep_time' + new_vn)
						.replace(/padding2/g, 'padding' + new_vn)
						.replace(/dest_paddingK/g, 'dest_padding' + new_vn)
						.replace(/total_hours2/g, 'total_hours' + new_vn)
						.replace(/add_dest2/g, 'add_dest' + new_vn)
						.replace(/delete_dest2/g, 'delete_dest' + new_vn);
//console.log(newHtml);
						
	var parentRow = $( '#' + e.currentTarget.id ).parents("tr:first");
	parentRow.after("<tr>" + newHtml + "</tr>\n");

	$("#destination" + new_vn).children().remove();
	$("#destination1").children().clone().appendTo($("#destination" + new_vn));

	// register all handlers
	$('select[id="destination' + new_vn + '"]').change(destinationHandler);
	$('input[id="padding' + new_vn + '"]').change(ttEntryChange);
	$('input[id="dest_padding' + new_vn + '"]').change(ttEntryChange);
	$('img[id="add_dest' + new_vn + '"]').click(addTimetableRow);
	$('img[id="delete_dest' + new_vn + '"]').click(deleteTimetableRow);
	//console.log($('input[id="dest_padding' + new_vn + '"]'));
	
	//disableAssignedFlights($('select[id="destination' + new_vn + '"]'), UnassignedFlightsOnly);

	//console.log("Finishing addTimetableRow(), entering ttEntryChange()");
	ttEntryChange(e);
}

function deleteTimetableRow(e)
{
	e.preventDefault();
	
	if ($("#timetable > tbody > tr").length == 1)
		return;
	
	var parentRow = $( '#' + e.currentTarget.id ).parents("tr:first");
	var tbody = parentRow.parents("tbody:first");
	
	// if first row, move form elements to second row
	index = parentRow.index();
	if (index === 0)
	{
		// destination cells
		old_start_day_cell = $('#timetable > tbody > tr:nth-child(1) > td:nth-child(4)');
		old_start_time_cell = $('#timetable > tbody > tr:nth-child(1) > td:nth-child(5)');

		new_start_day_cell = $('#timetable > tbody > tr:nth-child(2) > td:nth-child(4)');
		new_start_time_cell = $('#timetable > tbody > tr:nth-child(2) > td:nth-child(5)');
		
		// save selectors and copy to current row 2
		start_day_select = $('#start_day').clone();
		new_start_day_cell.empty();
		new_start_day_cell.append(start_day_select);
		
		start_time_select = $('#outbound_dep_time1').clone();
		start_time_select.val(new_start_time_cell.html());
		new_start_time_cell.empty();
		new_start_time_cell.append(start_time_select);

		
		// rename elements
		$('#destination2').attr({'id': 'destination1', 'name': 'destination1'});
		$('#dest_padding2').attr({'id': 'dest_padding1', 'name': 'dest_padding1'});
		$('#padding2').attr({'id': 'padding1', 'name': 'padding1'});
		$('#total_hours2').attr({'id': 'total_hours1', 'name': 'total_hours1'});
		$('#outbound_dep_time2').attr({'id': 'outbound_dep_time1', 'name': 'outbound_dep_time1'});
		

		$('#add_dest2').attr ('id', 'add_dest1');
		$('#delete_dest2').attr ('id', 'delete_dest1');	

		$('select[id^="destination"]').change(destinationHandler);
		$("#outbound_dep_time1").change(ttEntryChange);
		$('input[id^="padding"]').change(ttEntryChange);
		$('input[id^="dest_padding"]').change(ttEntryChange);
	}
	
	// now we delete row
	tbody[0].deleteRow(index);
	
	ttEntryChange(e);
}

/*
*/
function exportTableToJSON(e)
{
	e.preventDefault();
	
	var postData = { };

	game_id = postData.game_id = $('#game_id').val();
	postData.base_airport_iata = $('#base_airport_iata').val();
	postData.fleet_type_id = $('#fleet_type_id').val();
	timetable_id = "";
	
	// if we are currently looking at a timetable, send its timetable_id
	if (currentTimetableData.timetable_id !== undefined)
	{
		timetable_id = postData.timetable_id = currentTimetableData.timetable_id;
	}
	
	postData.base_turnaround_delta = MinutesToHHMM(HHMMtoMinutes($("#base_turnaround").val()) - HHMMtoMinutes($('#fleet_type_id')[0].selectedOptions[0].getAttribute('min_turnaround')));
	var entries = [];
	
	for (var index=1; index <= $("#timetable > tbody > tr").length; index++)
	{
		var flightData = {};
		var $row = $("#timetable > tbody > tr:nth-child(" + index + ")");
		
		// grab variable index from hidden value
		var vn = $row.find("td:nth-last-child(1) > input").attr("name").replace('total_hours', '');
		
		// flight number
		flightData.flight_number = $row.find("td:nth-child(1)").text();	

		// departure day
		if (index == 1)
			flightData.start_day = $("#start_day").val();
		else
			flightData.start_day = $row.find("td:nth-child(4)").text();
		
		// departure time
		if (index == 1)
			flightData.start_time = $('#outbound_dep_time1').val();
		else
			flightData.start_time = $row.find("td:nth-child(5)").text();
		
		// destination turnaround_length - zero for MTX, calculated otherwise
		if (flightData.flight_number == 'MTX')
			flightData.dest_turnaround_padding = "00:00";
		else
			flightData.dest_turnaround_padding = MinutesToHHMM(HHMMtoMinutes($("#dest_padding" + vn).val())); /*+ 
				HHMMtoMinutes($('#destination' + vn)[0].selectedOptions[0].getAttribute('turnaround_length')));*/
		
		// earliest available time
		flightData.earliest_available = $row.find("td:nth-child(11)").text();

		// padding
		flightData.post_padding = $("#padding" + vn).val();

		// destination - use the value attribute of the selected option, 
		// rather than .val(), in case it is a disabled option
		flightData.dest_airport_iata = $("#destination" + vn + " option:selected").attr('value');
		
		entries.push(flightData);
	}
	
	// add padding to the last entry to bring total time up to 168 hours
	//entries[entries.length - 1].post_padding = MinutesToHHMM(168 * 60 - TimetableTotal);
	
	postData.entries = entries; //JSON.stringify(entries, null, 4);
//alert(JSON.stringify(entries, null, 4));
//return;
	
	// choose a timetable name if none is set
	var nameSuggestion = $('#active_timetables option:selected').html();
	if (currentTimetableData.timetable_id === undefined)
	{
		// e.g. JFK-B736-01, JFK-B736-02 etc
		nameSuggestion = postData.base_airport_iata + "-" +
		$("#fleet_type_id")[0].selectedOptions[0].getAttribute('icao_code') + "-" + 
		sprintf("%02d", $("#active_timetables").children('[empty!=true]').length + 1);
	}
	
	var timetable_name = prompt("Enter timetable name", nameSuggestion);
	
	if (timetable_name === null || timetable_name.trim() === "")
		return;
	
	var complete = false;
	postData.timetable_name = timetable_name;
//	console.log(JSON.stringify(postData, null, 4));

	$.ajax({
		type: 'POST',
		//url: '/aws/timetable/add_timetable.php',
		url: 'http://localhost/aws/app/v1/games/' + game_id + '/timetables/' + timetable_id,
		data: JSON.stringify(postData),
		processData: false,
		dataType: 'json',
		
		error: function(jqXHR, textStatus, errorThrown) {
			alert(jqXHR.responseText );
			alert(textStatus);
			alert(errorThrown);
		}
	}).done(function (data)
	{
console.log(JSON.stringify(data, null, 4));
		alert("Added timetable [" + timetable_name + "] to database");
		complete = true;
		
		// ensures that subsequent saves use the timetable_id
		currentTimetableData.timetable_id = data.timetable_id[0];
		
		// add the new timetable to the select if it is brand new
		if (data.timetable_id[0] != $("#active_timetables").val())
		{
			var xk = $('<select></select>').html( 
			"<option " +
			"value='" + data.timetable_id[0] + "' " +
			"game_id='" + $("#game_id").val() + "' " +
			"base_airport_iata='" + $("#base_airport_iata").val() + "' " +
			"fleet_type_id='" + $("#fleet_type_id").val() + "'>" + 
			timetable_name + 
			"</option>").children();
			
			// add to dropdown and autoselect
			allActiveTimetables.push(xk);
			$("#active_timetables").append(xk);
			$("#active_timetables").val(data.timetable_id[0]);
			uri = data.href[0];
			
			$('#restful_uri').html("<a href='" + uri + "' target='_blank'>" + uri + "</a>");
	}
		else
		{
			// just change the text label
			$("#active_timetables :selected").text(timetable_name);
		}
	}).fail(function( jqXHR, textStatus, errorThrown )
	{
		alert("ERROR: " + jQuery.parseJSON(jqXHR.responseText).error);
	});

}

function exportTableToCSV($table, filename)
{
	var filename = ($('#active_timetables').val() != "" ? $('#active_timetables').val()+".csv" : 'timetable.csv');

	var $rows = $table.find('tr:has(td)'),

		// Temporary delimiter characters unlikely to be typed by keyboard
		// This is to avoid accidentally splitting the actual contents
		tmpColDelim = String.fromCharCode(11), // vertical tab character
		tmpRowDelim = String.fromCharCode(0), // null character

		// actual delimiter characters for CSV format
		colDelim = '","',
		rowDelim = '"\r\n"',

		// Grab text from table into CSV formatted string
		csv = '"' + $rows.map(function (i, row) {
			var $row = $(row),
				$cols = $row.find('td');

			return $cols.map(function (j, col) {
				var $col = $(col).clone(),
					child = $(col).children();
				$col.find("br").replaceWith(" ");
				var	text = $col.text().replace(/[\r\n]/g, '');
					
				if (typeof child !== 'undefined' && typeof child[0] !== 'undefined')
				{
					//console.log(child);
					
					if (child[0].tagName == 'SELECT')
					{
						text = child[0].selectedOptions[0].getAttribute('value');
						//alert("Found <SELECT>:" + child[0].getAttribute('id') + ", text = [" + text + "]");
					}
					else if (child[0].tagName == 'INPUT' && child[0].type != 'hidden')
					{
						text = child.val();
						//alert("Found <INPUT>: " + child[0].getAttribute('id') + ", value = [" + text + "]");
					}
					else
					{
					//alert(child[0].tagName);
					}

				}
				return text.replace('"', '""'); // escape double quotes

			}).get().join(tmpColDelim);

		}).get().join(tmpRowDelim)
			.split(tmpRowDelim).join(rowDelim)
			.split(tmpColDelim).join(colDelim) + '"',

		// Data URI
		csvData = 'data:application/csv;charset=utf-8,' + encodeURIComponent(csv);

	$(this)
		.attr({
		'download': filename,
			'href': csvData,
			'target': '_blank'
	});
}

function loadTimetable(e)
{
	e.preventDefault();
	
	if ($('#game_id').val() == "" || $('#active_timetables').val() == "")
	{
		//alert("game_id = " + $('#game_id').val() + ", " + $('#active_timetables').val());
		return false;
	}
	
	$("#spinner").toggle();
	
	retVal = getTimetable($('#game_id').val(), $('#active_timetables').val());
	
	$("#spinner").toggle();
	
	return retVal;
}


function getTimetable(game_id, timetable_id)
{
	
	var postData = {};
	postData.game_id = $('#game_id').val();
	postData.action = 'timetables';
	postData.base_airport_iata = $('#base_airport_iata').val();
	postData.fleet_type_id = $('#fleet_type_id').val();
	postData.timetable_id = $('#active_timetables').val();
	
	//alert(JSON.stringify(postData, null, 4));
	
	$.ajax({
		//type: 'POST',
		//url: '/aws/timetable/conflicts/conflicts.php',
		//data: postData,
		type: 'GET',
		url: 'http://localhost/aws/app/v1/games/' + game_id + '/timetables/' + timetable_id,
		dataType: 'json'
	}).done(function (data)
	{
//console.log(JSON.stringify(data, null, 4));
		if (data.error !== undefined)
		{
			alert("ERROR: " + data.error);
			return false;
		}
		
//console.log(JSON.stringify(data, null, 4));
		
		$("#timetable > tbody").find('tr').slice(1).remove();
		
		if (data.timetables[0].base_turnaround_delta === undefined)
		{
			$("#spinner").toggle();
			currentTimetableData = { };
			return;
		}
		
		currentTimetableData = data.timetables[0];

		// find the new base turnaround time by adding the returned delta
		var newBT = MinutesToHHMM(HHMMtoMinutes(data.timetables[0].base_turnaround_delta) + HHMMtoMinutes($('#fleet_type_id')[0].selectedOptions[0].getAttribute('min_turnaround')));
		$("#base_turnaround").val(newBT);
		
		flightsSeen = [];
		
		$( '#destination1' ).val("");
		ops_turnaround = HHMMtoMinutes($('#fleet_type_id')[0].selectedOptions[0].getAttribute('ops_turnaround'));

		
		// add each entry to the table from entries
		$.each(currentTimetableData.entries, function(idx, event)
		{
			if (idx === 0)
			{
				$('#outbound_dep_time1').val(event.start_time);
				$('#start_day').val(event.start_day);
			}
			else
			{
				$('#add_dest' + idx).trigger("click");
				//xkp($('#add_dest' + idx).parents('tr:first'));
			}
			$('#padding' + parseInt(idx + 1)).val(event.post_padding);
			
			// look out for dodgy turnaround_length values
			dest_turnaround_padding = HHMMtoMinutes(event.dest_turnaround_padding);
			
			//if (dest_turnaround_padding < ops_turnaround)
			//	dest_padding = "00:00";
			//else
				dest_padding = event.dest_turnaround_padding; //MinutesToHHMM(dest_turnaround_padding - ops_turnaround);
			
			$('#dest_padding' + parseInt(idx + 1)).val(dest_padding);
			
			flightsSeen.push(event.flight_number);
			
			// auto-select flight number
			opt = $('#destination' + parseInt(idx + 1)).find('[flight_number="' + event.flight_number + '"]');
			//console.log(opt, opt.length);
			if (opt[0] !== undefined)
				opt.prop('selected', true).change();
			//opt.addClass('inUse');
			//console.log("enabling "+event.flight_number);
			//opt.prop('disabled', false);
			//opt.removeAttr('disabled');
		//alert("value = " + allDestinations.clone().filter('[flight_number="' + event.flight_number + '"]').getAttribute('value'));
			//$('#destination' + parseInt(idx + 1)).val(event.flight_number).change();
		});
		
		filter = flightsSeen.map(function (flight) {
			return "[flight_number='" + flight + "']"
		}).join(",");
		
		//console.log(filter);

		
/*		$('select[id^=destination]').find(filter).prop('selected', true).change();
		$('select[id^=destination]').find(filter).addClass('inUse');*/
		$('select[id^=destination]').find(filter).prop('disabled', false);
		$('select[id^=destination]').find(filter).removeAttr('disabled');

		
		uri = 'http://localhost/aws/app/v1/games/' + game_id + '/timetables/' + timetable_id + ".html";
		
		$('#restful_uri').html("<a href='" + uri + "' target='_blank'>" + uri + "</a>");
	});	
	
}

var currentTimetableData = {};
$(document).ready(function ()
{
	getFormOptions(function()
	{
		allBases.clone().filter('[empty="true"]').appendTo($("#base_airport_iata"));
/*		allFleetTypes.clone().filter('[empty="true"]').appendTo($("#fleet_type_id"));
		allActiveTimetables.clone().filter('[empty="true"]').appendTo($("#active_timetables"));
		allDestinations.clone().filter('[empty="true"]').appendTo('select[name^="destination"]');
*/
		// create second row template
		var r = $("#destination2").parents("tbody > tr:nth-child(2)");
		rowTemplate = r.html();
		r.remove();
	});
	
	$("#spinner").hide();
	
	$('#timetable > tbody').sortable({
		stop: function(event, ui) {
			//console.log("event: "+event.type + "; item: ["+ui.item.html()+"]");

			ttEntryChange(event);
		}
	});

    // This must be a hyperlink
    $("#exportCSV").on('click', function (event) {
        // CSV
        exportTableToCSV.apply(this, [$('#timetable'), 'timetable.csv']);
        
        // IF CSV, don't do event.preventDefault() or return false
        // We actually need this to be a typical hyperlink
    });
	
	$("#loadTimetable").on('click', loadTimetable);
	$("#exportJSON").on('click', exportTableToJSON);
	$("#clearTT").on('click', function(event) {
		event.preventDefault();
		clearTimetable();
	});

	$('#exportCSV').attr('disabled', true);
	$('#exportJSON').attr('disabled', true);
	$('#loadTimetable').attr('disabled', true);
	
	$("#refreshBtn").click(refreshHandler);
	
	//rowTemplate = $("#timetable > tbody > tr:nth-child(2)").html();
	//$("#timetable > tbody > tr:nth-child(2)").remove();
	
	$("#base_airport_iata").children('[empty!="true"]').remove();
	$("#fleet_type_id").children('[empty!="true"]').remove();
	$("#active_timetables").children('[empty!="true"]').remove();

	
    $("#game_id").change(formFilterHandler);
	$("#base_airport_iata").change(formFilterHandler);
	$("#fleet_type_id").change(formFilterHandler);

	//$('select[name^="destination"]').append(allDestinations);
	//$('select[name^="destination"]').children('[empty!="true"]').remove();
	
	//var r = $("#destination2").parents("tbody > tr:nth-child(2)");
	//rowTemplate = r.html();
	//r.remove();
	
	$('#start_day').change(ttEntryChange);
	
	$('select[id^="destination"]').change(destinationHandler);
	$("#outbound_dep_time1").change(ttEntryChange);
	$('input[id^="padding"]').change(ttEntryChange);
	$('input[id^="dest_padding"]').change(ttEntryChange);
	$('#base_turnaround').change(ttEntryChange);
	$('#active_timetables').change(enableLoadButton);	
	$("img[id^=add_dest]").click(addTimetableRow);
	$("img[id^=delete_dest]").click(deleteTimetableRow);
	
	$('#unassigned_only').change(toggleUnassigned);
	//$('#unassigned_only').click(toggleUnassigned);
	
	timetable_id = getUrlParameter('tid');
	game_id = getUrlParameter('gid');

	//console.log("timetable_id = "+timetable_id+", game_id = "+game_id);
	if (timetable_id !== undefined && game_id !== undefined)
	{
		//getTimetable(game_id, timetable_id);
	}

	
});
	
