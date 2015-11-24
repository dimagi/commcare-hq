function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}

function setAjaxCsrfHeader(xhr, settings) {
	// Don't pass csrftoken cross domain
	if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
	    $csrf_token = $.cookie('csrftoken');
	    xhr.setRequestHeader("X-CSRFToken", $csrf_token);
	}
}