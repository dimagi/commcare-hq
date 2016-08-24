/*global Backbone, FormplayerFrontend */

function Util() {
}

Util.encodedUrlToObject = function (encodedUrl) {
    return decodeURIComponent(encodedUrl);
};

Util.objectToEncodedUrl = function (object) {
    return encodeURIComponent(object);
};

Util.currentUrlToObject = function () {
    var url = Backbone.history.getFragment();
    return Util.CloudcareUrl.fromJson(Util.encodedUrlToObject(url));
};

Util.setUrlToObject = function (urlObject) {
    var encodedUrl = Util.objectToEncodedUrl(urlObject.toJson());
    FormplayerFrontend.navigate(encodedUrl);
};

Util.doUrlAction = function(actionCallback) {
    var currentObject = Util.CurrentUrlToObject();
    actionCallback(currentObject);
    Util.setUrlToObject(currentObject);
};

Util.setCrossDomainAjaxOptions = function (options) {
    options.type = 'POST';
    options.dataType = "json";
    options.crossDomain = {crossDomain: true};
    options.xhrFields = {withCredentials: true};
    options.contentType = "application/json";
};

Util.CloudcareUrl = function (appId, options) {
    options = options || {};
    this.appId = appId;
    this.sessionId = options.sessionId;
    this.steps = options.steps;
    this.page = options.page;
    this.search = options.search;
    this.queryDict = options.queryDict;
    this.singleApp = options.singleApp;
    this.previewCommand = options.previewCommand;

    this.addStep = function (step) {
        if (!this.steps) {
            this.steps = [];
        }
        this.steps.push(step);
        //clear out pagination and search when we take a step
        this.page = null;
        this.search= null;
    };

    this.setPage = function (page) {
        this.page = page;
    };

    this.setSearch = function (search) {
        this.search = search;
        //clear out pagination on search
        this.page = null;
    };

    this.setSessionId = function (sessionId) {
        this.sessionId = sessionId;
        this.steps = null;
        this.page = null;
        this.search= null;
    };

    this.setQuery = function(queryDict) {
        this.queryDict = queryDict;
    };

    this.clearExceptApp = function () {
        this.sessionId = null;
        this.steps = null;
        this.page = null;
        this.search= null;
        this.queryDict = null;
    };

    this.spliceSteps = function(index) {

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
    };
};

Util.CloudcareUrl.prototype.toJson = function () {
    var self = this;
    var dict = {
        appId: self.appId,
        sessionId: self.sessionId,
        steps: self.steps,
        page: self.page,
        search: self.search,
        queryDict: self.queryDict,
        previewCommand: self.previewCommand,
    };
    return JSON.stringify(dict);
};

Util.CloudcareUrl.fromJson = function (json) {
    var data = JSON.parse(json);
    var options = {
        'sessionId': data.sessionId,
        'steps': data.steps,
        'page': data.page,
        'search': data.search,
        'queryDict': data.queryDict,
        'singleApp': data.singleApp,
        'previewCommand': data.previewCommand,
    };
    return new Util.CloudcareUrl(
        data.appId,
        options
    );
};

if (!String.prototype.startsWith) {
    String.prototype.startsWith = function(searchString, position) {
        position = position || 0;
        return this.substr(position, searchString.length) === searchString;
    };
}
