hqDefine("cloudcare/js/formplayer/errors", function () {
    return {
        GENERIC_ERROR: gettext("Something unexpected went wrong on that request. " +
            "If you have problems filling in the rest of your form please submit an issue. " +
            "Technical Details: "),
        TIMEOUT_ERROR: gettext("CommCareHQ has detected a possible network connectivity problem. " +
            "Please make sure you are connected to the " +
            "Internet in order to submit your form."),
        LOCK_TIMEOUT_ERROR: gettext('Another process prevented us from servicing your request. ' +
            'Please try again later.'),
        NO_INTERNET_ERROR: gettext("We have detected an issue with your network. " +
            "Please check your Internet connection and retry when connectivity " +
            "improves."),
    };
});
