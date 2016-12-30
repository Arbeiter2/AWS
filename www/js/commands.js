var allBases = null;
var allFleetTypes = null;
var allActiveTimetables = null;


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
		for (field in data[i])
		{
			if (field == textFieldName || field == valueFieldName)
				continue;
			
			opt.setAttribute(field, data[i][field]);
		}
		output.push(opt);
//		console.log(opt);
	}
	return output;
}

var cmdBtn;
/*
function getFormOptions(callback)
{
//	console.log("In getFormOptions())");
	
	var postData = { 'action' : 'game_options' };
	$.ajax({
		type: 'POST',
		url: '/aws/timetable/conflicts/conflicts.php',
		data: postData,
		dataType: 'json'
	}).done(function (response)
	{

		var b = buildOptionList(response.bases_json, 'option_text', 'base_airport_iata');
		var g = buildOptionList(response.games_json, 'name', 'game_id');
//			console.log(JSON.stringify(t, null, 4));
		$('#game_id').empty();
		$('#game_id').append(g);

		//$('#base_airport_iata').empty();
		bs = $('<select></select>').append(b);
		allBases = bs.children().clone();
		
		if (callback !== undefined)
			callback();
	});	
}
*/


function getFormOptions(callback)
{
//	console.log("In getFormOptions())");
	
	var postData = { 'action' : 'game_options' };
	$.ajax({
		type: 'GET',
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

function getAvailableFlightsFromBase(callback)
{
	game_id = $('#game_id').val();
	base_airport_iata = $('#base_airport_iata').val();
	if (game_id === null || base_airport_iata === null)
		return;
	
	$.ajax({
		type: 'GET',
		url: 'http://localhost/aws/app/v1/games/' + game_id + '/flights/' + base_airport_iata,
		dataType: 'json'
	}).done(function (flightData)
	{
//		console.log(JSON.stringify(flightData.fleet_types, null, 4));
		

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
			var timetables = buildOptionList(timetableData.timetables, 'timetable_name', 'timetable_id');
			var ts = $('<select></select>').append(timetables);
			allActiveTimetables = ts.children().clone();
	//		console.log(allActiveTimetables);
		});
		
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
//console.log(flightsSeen);

	getFormOptions(function() 
	{
		// now reset the values of the top level form
		$('#game_id').val(formValues.game_id);

		//$("#base_airport_iata").children().remove();
		$("#base_airport_iata").children('[empty!="true"]').remove();
		allBases.clone().filter('[game_id="' + $('#game_id').val() + '"]').appendTo($("#base_airport_iata"));
		$('#base_airport_iata').val(formValues.base_airport_iata);
	});
	
	getFleetTypes(function() 
	{
		clearFleetTypes();
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
		

		var timetables = buildOptionList(flightData.timetables, 'timetable_name', 'timetable_id');
		var ts = $('<select></select>').append(timetables);
		allActiveTimetables = ts.children().clone();
//		console.log(allActiveTimetables);


		if (callback !== undefined)
			callback();
	});		
}
*/

function formFilterHandler(e)
{
	e.preventDefault();

	switch (e.currentTarget.name)
	{
	case 'fleet_type_id':
		clearDestinations();
		break;
		
	case 'base_airport_iata':
		getAvailableFlightsFromBase(function() {
			clearFleetTypes();
		});
		break;
		
	case 'game_id':
		getFleetTypes(function() {
			clearBases();
		});
		break;
	}
}


function clearDestinations()
{
	if (allActiveTimetables != null)
	{
		$('#timetable_id').children().remove();
		allActiveTimetables.clone().filter('[empty="true"]').appendTo($('#timetable_id'));	
		
		allActiveTimetables.clone().filter('[game_id="' + $('#game_id').val() + '"][base_airport_iata="' + $('#base_airport_iata').val() + '"][fleet_type_id="' + $('#fleet_type_id').val() + '"]').appendTo($('#timetable_id'));
	}
}


function clearFleetTypes()
{
	$("#fleet_type_id").children().remove();
	
	if (allFleetTypes != null)
	{
		allFleetTypes.clone().filter('[empty="true"]').appendTo($("#fleet_type_id"));
		allFleetTypes.clone().filter('[game_id="' + $('#game_id').val() + '"][base_airport_iata="' + $('#base_airport_iata').val() + '"]').appendTo($("#fleet_type_id"));
	}
}

function clearBases()
{
	var game_id = $('#game_id').val();
	$("#base_airport_iata").children('[empty!="true"]').remove();
	if (allBases != null)
		allBases.clone().filter('[game_id="' + game_id + '"]').appendTo($("#base_airport_iata"));
	clearFleetTypes();
}


function AddJson()
{
	var instance = new Array(6).join().replace(/(.|$)/g, function(){return ((Math.random()*36)|0).toString(36)[Math.random()<0.5?"toString":"toUpperCase"]();});
	
	// allows a sequence of objects from different games to be pasted together, so turns them into an array
	var t = '[' + $('#flight_json_text').val().replace(/}\s*{/g, '},{') + ']';
	var data = jQuery.parseJSON(t);
	
	/*
	//console.log("data: "+JSON.stringify(data));
	//console.log("data: "+JSON.stringify(data[0]));
	
	// group flights by game_id
	var postData = {};
	var gameIDs = {};
	
	for (i=0; i < data.length; i++)
	{
		var game_id = data[0].game_id;
		
		// add this game_id to the list to be processed
		if (gameIDs[game_id] === undefined)
		{
			gameIDs[game_id] = 1;
			postData["g_" + game_id] = { game_id : game_id, newFlightData : {} };
		}
		
		postData["g_" + game_id].newFlightData["fl_" +  data[i].flight_id] = data[i];
	}

	for (key in postData)
	{
		game_id = key.replace(/\D+/, '');
		
		//console.log(JSON.stringify(postData[key], null, 4));

			
		$.ajax({
			type: 'POST',
			url: '/aws/add_routes.php',
			data: 
			{ 
				game_id : game_id, 
				instance : instance,
				newFlightData : JSON.stringify(postData[key].newFlightData) 
			},
			dataType: 'json'
		}).done(function (response)
		{
			//console.log(response);
			//$('#viewer').append("Added routes for game_id [" + game_id + "]<br>");
			$('#viewer').append("Added [" + response.flight_numbers.join(', ') + "]<br>");
		});	
	}*/
	//console.log(t);
	var game_id = $('#game_id').val();
	$.ajax({
		type: 'POST',
		url: '/aws/app/v1/games/' + game_id + '/flights',
		processData: false,
		data: t,
		dataType: 'json',
		error: function ( jqXHR, textStatus, errorThrown )
		{
			$('#viewer').append("Error " + errorThrown + "; " + textStatus);
		}
	}).done(function (response)
	{
		//console.log(response);
		//$('#viewer').append("Added routes for game_id [" + game_id + "]<br>");
		//$('#viewer').append("Added [" + response.flight_numbers.join(', ') + "]<br>");
	});	
}

// handlers for button
function ControlCommand(event)
{
	event.preventDefault();
	
	if ($('#command').val() === 'add_json')
	{
		AddJson();
		return;
	}
	
	var lastCommand = (cmdBtn.html() === "Run" ? "start" : "stop");

	var formData = $('#cthulhu').serializeObject();
	formData['action'] = lastCommand;
console.log("starting...");

    $.ajax({
	
	dataFilter: function (data, type)
	{
		$('#viewer').html( unescapeHtml(data) );
		return data;				
	},
	
        xhr: function() {
			var xhr = $.ajaxSettings.xhr();
            xhr.addEventListener("progress", 
			function(evt) 
			{
				var lines = evt.currentTarget.response.split("\n");
				if(lines.length)
					var progress = lines[lines.length-1];
				else
					var progress = 0;
//				console.log(lines);
				$('#viewer').html( unescapeHtml(progress) );
            }, false);
			
			xhr.addEventListener("loadstart",
			function(evt)
			{
				//alert('data transfer started');
				if (lastCommand == "start")
				{
					cmdBtn.removeClass('blueBtn');
					cmdBtn.addClass('redBtn');
					cmdBtn.html("Stop");
				}
				else
				{
				}
			}, false);

			xhr.addEventListener("loadend",
			function(evt)
			{
				//alert('data transfer complete');
				cmdBtn.removeClass('redBtn');
				cmdBtn.addClass('blueBtn');
				cmdBtn.html("Run");
			}, false);			
           return xhr;
        },          
        
		type: 'POST',
		
		data: formData,
		
        url: "aws_commands.php",
        
		error: function (xhr, ajaxOptions, thrownError) {
                  if (xhr.status == 500) {
                      alert('Internal error: ' + jqXHR.responseText);
                  } else {
                      alert('Unexpected error.');
                  }
            $('#viewer').text("Error");
        }
    }); 
}

$(document).ready(function ()
{
	getFormOptions(function()
	{
		allBases.clone().filter('[empty="true"]').appendTo($("#base_airport_iata"));
	});

    $("#game_id").change(formFilterHandler);
	$("#base_airport_iata").change(formFilterHandler);
	$("#fleet_type_id").change(formFilterHandler);	
	$('#cmdBtn').click(ControlCommand);
	$("#refreshBtn").click(refreshHandler);
	
	$( ".conditional" ).hide( );
	cmdBtn = $('#cmdBtn');

	$( "#command" ).change(function() {
	  $( ".conditional" ).hide( );
	  
	  var selector = "tr[id*='" + $( "#command" ).val() + "-']";
	  var x = $( selector );
	  x.show( );
	  cmdBtn.attr("disabled", ($( "#command" ).val() == "---"));
	  
	});

	//cmdBtn.attr("disabled", true);

});