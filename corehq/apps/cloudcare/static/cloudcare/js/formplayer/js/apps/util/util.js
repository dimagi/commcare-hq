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

Util.CloudcareUrl = function (appId, sessionId, steps, page, search) {
    this.appId = appId;
    this.sessionId = sessionId;
    this.steps = steps;
    this.page = page;
    this.search = search;

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

    this.clearExceptApp = function () {
        this.sessionId = null;
        this.steps = null;
        this.page = null;
        this.search= null;
    };

    this.spliceSteps = function(index) {
        this.steps = this.steps.splice(0, index);
    }
};

Util.CloudcareUrl.prototype.toJson = function () {
    var self = this;
    var dict = {
        appId: self.appId,
        sessionId: self.sessionId,
        steps: self.steps,
        page: self.page,
        search: self.search,
    };
    return JSON.stringify(dict);
};

Util.CloudcareUrl.fromJson = function (json) {
    var data = JSON.parse(json);
    return new Util.CloudcareUrl(data.appId, data.sessionId, data.steps, data.page, data.search);
};