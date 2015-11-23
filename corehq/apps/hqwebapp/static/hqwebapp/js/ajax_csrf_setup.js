function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}

function setAjaxCsrfHeader(xhr, settings) {
	$csrf_token = $.cookie('csrftoken');

	if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
	    // Don't pass csrftoken cross domain
	    xhr.setRequestHeader("X-CSRFToken", $csrf_token);
	}
}