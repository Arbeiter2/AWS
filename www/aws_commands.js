{
	"price_update" :
	{
		"script_name" : "price_update.js",
		"options" :
		[ 
			{ "name" : "keyword", "isMandatory" : true, "isFlag" : false },
			{ "name" : "delta", "isMandatory" : false, "isFlag" : false }
		]
	},

	"next" :
	{
		"script_name" : "next.js",
		"options" :
		[ 
			{ "name" : "slots", "isMandatory" : false, "isFlag" : true },
			{ "name" : "from-aircraft", "isMandatory" : true, "isFlag" : false },
			{ "name" : "to-aircraft", "isMandatory" : false, "isFlag" : false }
		]
	},
	
	"fleet_type_change" :
	{
		"script_name" : "fleet_type_change.js",
		"options" :
		[ 
			{ "name" : "from-aircraft", "isMandatory" : true, "isFlag" : false },
			{ "name" : "to-aircraft", "isMandatory" : false, "isFlag" : false },
			{ "name" : "fleet_type", "isMandatory" : true, "isFlag" : false }
		]
	},
	
	"flights" :
	{
		"script_name" : "stats.js",
		"options" :
		[ 
		]
	},
	
	"renumber" :
	{
		"script_name" : "renumber.js",
		"options" :
		[
			{ "name" : "from", "isMandatory" : true, "isFlag" : false },
			{ "name" : "to", "isMandatory" : true, "isFlag" : false }		
		]
	},
	
	"retime" :
	{
		"script_name" : "retime.js",
		"options" :
		[
			{ "name" : "flight", "isMandatory" : true, "isFlag" : false },
			{ "name" : "new-time", "isMandatory" : true, "isFlag" : false },
			{ "name" : "new-day", "isMandatory" : false, "isFlag" : false },
			{ "name" : "slots", "isMandatory" : false, "isFlag" : true }
		]
	},
	
	"timetable_to_aircraft" :
	{
		"script_name" : "timetable_to_aircraft.js",
		"options" :
		[
			{ "name" : "timetable_id", "isMandatory" : true, "isFlag" : false },
			{ "name" : "to-aircraft", "isMandatory" : true, "isFlag" : false }
		]
	},

	"retime_timetable" :
	{
		"script_name" : "retime_timetable.js",
		"options" :
		[
			{ "name" : "timetable_id", "isMandatory" : true, "isFlag" : false },
			{ "name" : "slots", "isMandatory" : false, "isFlag" : true }
		]
	},
	
	"aircraft" :
	{
		"script_name" : "aircraft.js",
		"options" :
		[ 
		]
	},

	"timetable_stats" :
	{
		"script_name" : "timetable_gaps.js",
		"options" :
		[ 
		]
	}	
}
