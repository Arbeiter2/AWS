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
/*
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
};*/