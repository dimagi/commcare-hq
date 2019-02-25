/*global Backbone, FormplayerFrontend, DOMPurify */

function Util() {
}

/**
 * confirmationModal
 *
 * Takes an options hash that specifies options for a confirmation modal.
 *
 * @param options - Object
 *      {
 *          'title': <title> | 'Confirm?',
 *          'message': <message>,
 *          'confirmText': <confirmText> | 'OK',
 *          'cancelText': <cancelText> | 'Cancel',
 *          'onConfirm': function() {},
 *      }
 */
Util.confirmationModal = function (options) {
    options = _.defaults(options, {
        title: gettext('Confirm?'),
        message: '',
        confirmText: gettext('OK'),
        cancelText: gettext('Cancel'),
        onConfirm: function () {},
    });
    var $modal = $('#js-confirmation-modal');
    $modal.find('.js-modal-title').text(options.title);
    $modal.find('.js-modal-body').html(DOMPurify.sanitize(options.message));
    $modal.find('#js-confirmation-confirm').text(options.confirmText);
    $modal.find('#js-confirmation-cancel').text(options.cancelText);

    $modal.find('#js-confirmation-confirm').click(function (e) {
        options.onConfirm(e);
    });
    $modal.modal('show');
};

Util.encodedUrlToObject = function (encodedUrl) {
    return decodeURIComponent(encodedUrl);
};

Util.objectToEncodedUrl = function (object) {
    return encodeURIComponent(object);
};

Util.currentUrlToObject = function () {
    var url = Backbone.history.getFragment();
    try {
        return Util.CloudcareUrl.fromJson(Util.encodedUrlToObject(url));
    } catch (e) {
        // This means that we're on the homepage
        return new Util.CloudcareUrl({});
    }
};

Util.setUrlToObject = function (urlObject, replace) {
    replace = replace || false;
    var encodedUrl = Util.objectToEncodedUrl(urlObject.toJson());
    FormplayerFrontend.navigate(encodedUrl, { replace: replace });
};

Util.doUrlAction = function (actionCallback) {
    var currentObject = Util.CurrentUrlToObject();
    actionCallback(currentObject);
    Util.setUrlToObject(currentObject);
};

Util.setCrossDomainAjaxOptions = function (options) {
    options.type = 'POST';
    options.dataType = "json";
    options.crossDomain = {crossDomain: true};
    options.xhrFields = {withCredentials: true};
    options.contentType = "application/json;charset=UTF-8";
};

Util.saveDisplayOptions = function (displayOptions) {
    var displayOptionsKey = Util.getDisplayOptionsKey();
    localStorage.setItem(displayOptionsKey, JSON.stringify(displayOptions));
};

Util.getSavedDisplayOptions = function () {
    var displayOptionsKey = Util.getDisplayOptionsKey();
    try {
        return JSON.parse(localStorage.getItem(displayOptionsKey));
    } catch (e) {
        window.console.warn('Unabled to parse saved display options');
        return {};
    }
};

Util.getDisplayOptionsKey = function () {
    var user = FormplayerFrontend.request('currentUser');
    return [
        user.environment,
        user.domain,
        user.username,
        'displayOptions',
    ].join(':');
};

Util.pagesToShow = function (selectedPage, totalPages, limit) {
    var limitHalf = Math.floor(limit / 2);
    if (totalPages < limit) {
        return {
            start: 0,
            end: totalPages,
        };
    }

    if (selectedPage < limitHalf) {
        return {
            start: 0,
            end: limit,
        };
    }

    if (selectedPage > totalPages - limitHalf) {
        return {
            start: totalPages - limit,
            end: totalPages,
        };
    }

    return {
        start: selectedPage - limitHalf,
        end: selectedPage + limitHalf,
    };
};

Util.CloudcareUrl = function (options) {
    this.appId = options.appId;
    this.copyOf = options.copyOf;
    this.sessionId = options.sessionId;
    this.steps = options.steps;
    this.page = options.page;
    this.search = options.search;
    this.queryDict = options.queryDict;
    this.singleApp = options.singleApp;
    this.installReference = options.installReference;
    this.sortIndex = options.sortIndex;

    this.setSteps = function (steps) {
        this.steps = steps;
    };

    this.addStep = function (step) {
        if (!this.steps) {
            this.steps = [];
        }
        this.steps.push(step);
        //clear out pagination and search when we take a step
        this.page = null;
        this.search = null;
    };

    this.setPage = function (page) {
        this.page = page;
    };

    this.setSort = function (sortIndex) {
        this.sortIndex = sortIndex;
    };


    this.setSearch = function (search) {
        this.search = search;
        //clear out pagination on search
        this.page = null;
        this.sortIndex = null;
    };

    this.setQuery = function (queryDict) {
        this.queryDict = queryDict;
    };

    this.clearExceptApp = function () {
        this.sessionId = null;
        this.steps = null;
        this.page = null;
        this.sortIndex = null;
        this.search = null;
        this.queryDict = null;
    };

    this.onSubmit = function () {
        this.page = null;
        this.sortIndex = null;
        this.search = null;
        this.queryDict = null;
    };

    this.spliceSteps = function (index) {

        // null out the session if we clicked the root (home)
        if (index === 0) {
            this.steps = null;
            this.sessionId = null;
        } else {
            this.steps = this.steps.splice(0, index);
        }
        this.page = null;
        this.search = null;
        this.queryDict = null;
        this.sortIndex = null;
    };
};

Util.CloudcareUrl.prototype.toJson = function () {
    var self = this;
    var dict = {
        appId: self.appId,
        copyOf: self.copyOf,
        sessionId: self.sessionId,
        steps: self.steps,
        page: self.page,
        search: self.search,
        queryDict: self.queryDict,
        singleApp: self.singleApp,
        installReference: self.installReference,
        sortIndex: self.sortIndex,
    };
    return JSON.stringify(dict);
};

Util.CloudcareUrl.fromJson = function (json) {
    var data = JSON.parse(json);
    var options = {
        'appId': data.appId,
        'copyOf': data.copyOf,
        'sessionId': data.sessionId,
        'steps': data.steps,
        'page': data.page,
        'search': data.search,
        'queryDict': data.queryDict,
        'singleApp': data.singleApp,
        'installReference': data.installReference,
        'sortIndex': data.sortIndex,
    };
    return new Util.CloudcareUrl(options);
};

if (!String.prototype.startsWith) {
    String.prototype.startsWith = function (searchString, position) {
        position = position || 0;
        return this.substr(position, searchString.length) === searchString;
    };
}

if (!String.prototype.endsWith) {
    String.prototype.endsWith = function (searchString, position) {
        var subjectString = this.toString();
        if (typeof position !== 'number' || !isFinite(position) || Math.floor(position) !== position || position > subjectString.length) {
            position = subjectString.length;
        }
        position -= searchString.length;
        var lastIndex = subjectString.lastIndexOf(searchString, position);
        return lastIndex !== -1 && lastIndex === position;
    };
}

if (!String.prototype.includes) {
    String.prototype.includes = function (search, start) {
        'use strict';
        if (typeof start !== 'number') {
            start = 0;
        }
        if (start + search.length > this.length) {
            return false;
        } else {
            return this.indexOf(search, start) !== -1;
        }
    };
}

if (!String.prototype.repeat) {
    String.prototype.repeat = function (count) {
        var result = "", string = this.valueOf();
        while (count > 0) {
            result += string;
            count -= 1;
        }
        return result;
    };
}
