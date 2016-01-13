if (!String.prototype.startsWith) {
    String.prototype.startsWith = function(searchString, position) {
        position = position || 0;
        return this.indexOf(searchString, position) === position;
    };
}

NProgress.configure({
    showSpinner: false,
});

var getLocalizedString = function (property, language) {
    // simple utility to localize a string based on a dict of 
    // language mappings.
    return localize(this.get(property), language);
};

var localize = function(obj, language) {
    var s = obj[language];
    if (!s) {
        for (var lang in obj) {
            if (obj.hasOwnProperty(lang) && obj[lang]) {
                s = obj[lang];
                break;
            }
        }
    }
    return s || localize.NOT_FOUND;
};
localize.NOT_FOUND = '?';

var getFormUrl = function(urlRoot, appId, moduleId, formId, instanceId) {
    // TODO: make this cleaner
    var url = urlRoot + "view/" + appId + "/modules-" + moduleId + "/forms-" + formId + "/context/";
    if (instanceId) {
        url += '?instance_id=' + instanceId;
    }
    return url
};

var getFormEntryUrl = function (urlRoot, appId, moduleId, formId, caseId) {
    return urlRoot + getFormEntryPath(appId, moduleId, formId, caseId);
}
var getChildSelectUrl = function(urlRoot, appId, moduleId, formId, parentId){
    return urlRoot + getChildSelectPath(appId, moduleId, formId, parentId);
}
var getChildSelectPath = function(appId, moduleId, formId, parentId){
    return "view/" + appId + "/" + moduleId + "/" + formId + "/parent/" + parentId;
}

var getFormEntryPath = function(appId, moduleId, formId, caseId) {
    // TODO: make this cleaner
    var url = "view/" + appId + "/" + moduleId + "/" + formId;
    if (caseId) {
        url = url + '/case/' + caseId
    }
    url += "/enter/";
    return url;
};

var getSubmitUrl = function (urlRoot, appId) {
    // deprecated but still called from "touchforms-inline"
    // which is used to fill out forms from within case details view
    // use app.getSubmitUrl instead
    // todo: replace and remove
    return urlRoot + "/" + appId + "/";
};

var getCaseFilterUrl = function(urlRoot, appId, moduleId, special, parentId) {
    // TODO: make this cleaner
    var url = urlRoot + "module/" + appId + "/modules-" + moduleId + "/";
    if (parentId){
        url += "parent/" + parentId + "/";
    }
    if (special === 'task-list') {
        url += '?task-list=true';
    }
    return url
};

var getSessionContextUrl = function(sessionUrlRoot, session_id) {
    // TODO: make this cleaner
    return sessionUrlRoot + session_id;
};

var isParentField = function(field) {
    return field ? field.startsWith('parent/') : false;
};

var showError = function (message, location, autoHideTime) {
    if (message === undefined) {
        message = "sorry, there was an error";
    }
    _show(message, location, autoHideTime, "alert alert-danger");
};

var showSuccess = function (message, location, autoHideTime) {
    if (message === undefined) {
        message = "success";
    }
    _show(message, location, autoHideTime, "alert alert-success");
};

var _show = function (message, location, autoHideTime, classes) {
    var alert = $("<div />");
    alert.addClass(classes).text(message);
    alert.append($("<a />").addClass("close").attr("data-dismiss", "alert").html("&times;"));
    location.append(alert);
    if (autoHideTime) {
        alert.delay(autoHideTime).fadeOut(500);
    }
};

var showLoading = function (selector) {
    NProgress.start();
};

var tfLoading = function (selector) {
    showLoading();
};

var hideLoading = function (selector) {
    selector = selector || "#loading";
    $(selector).hide();
};

var tfLoadingComplete = function (isError) {
    hideLoading();
    if (isError) {
        showError(translatedStrings.errSaving, $('#cloudcare-notifications'));
    }
};

var tfSyncComplete = function (isError) {
    hideLoading();
    if (isError) {
        showError(translatedStrings.errSyncing, $('#cloudcare-notifications'));
    } else {
        showSuccess(translatedStrings.synced, $('#cloudcare-notifications'), 5000);
    }
};

var hideLoading = function (selector) {
    NProgress.done();
};

var hideLoadingCallback = function () {
    hideLoading();
};
