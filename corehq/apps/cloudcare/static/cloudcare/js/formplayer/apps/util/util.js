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
    try {
        return Util.CloudcareUrl.fromJson(Util.encodedUrlToObject(url));
    } catch (e) {
        // This means that we're on the homepage
        return new Util.CloudcareUrl({});
    }
};

Util.setUrlToObject = function (urlObject) {
    var encodedUrl = Util.objectToEncodedUrl(urlObject.toJson());
    FormplayerFrontend.navigate(encodedUrl);
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
    options.contentType = "application/json";
};

Util.CloudcareUrl = function (options) {
    this.appId = options.appId;
    this.sessionId = options.sessionId;
    this.steps = options.steps;
    this.page = options.page;
    this.search = options.search;
    this.queryDict = options.queryDict;
    this.singleApp = options.singleApp;
    this.previewCommand = options.previewCommand;
    this.installReference = options.installReference;

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

    this.setSearch = function (search) {
        this.search = search;
        //clear out pagination on search
        this.page = null;
    };

    this.setSessionId = function (sessionId) {
        this.sessionId = sessionId;
        this.steps = null;
        this.page = null;
        this.search = null;
    };

    this.setQuery = function (queryDict) {
        this.queryDict = queryDict;
    };

    this.clearExceptApp = function () {
        this.sessionId = null;
        this.steps = null;
        this.page = null;
        this.search = null;
        this.queryDict = null;
        this.previewCommand = null;
    };

    this.onSubmit = function () {
        this.steps = null;
        this.page = null;
        this.search = null;
        this.queryDict = null;
        this.previewCommand = null;
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
        singleApp: self.singleApp,
        previewCommand: self.previewCommand,
        installReference: self.installReference,
    };
    return JSON.stringify(dict);
};

Util.CloudcareUrl.fromJson = function (json) {
    var data = JSON.parse(json);
    var options = {
        'appId': data.appId,
        'sessionId': data.sessionId,
        'steps': data.steps,
        'page': data.page,
        'search': data.search,
        'queryDict': data.queryDict,
        'singleApp': data.singleApp,
        'previewCommand': data.previewCommand,
        'installReference': data.installReference,
    };
    return new Util.CloudcareUrl(options);
};

if (!String.prototype.startsWith) {
    String.prototype.startsWith = function (searchString, position) {
        position = position || 0;
        return this.substr(position, searchString.length) === searchString;
    };
}
