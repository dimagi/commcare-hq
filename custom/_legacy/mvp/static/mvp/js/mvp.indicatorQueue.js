window.mvp = {};

mvp.MVPIndicatorQueue = function (queueLength, fnProcessNextCallback) {
    'use strict';
    var self = this;
    self.qIndex = -1;
    self.queueLength = queueLength;
    self.d = null;

    self.start = function () {
        self.d = $.Deferred();
        self.next();
    };

    self.next = function () {
        self.qIndex ++;
        var indicators = ko.utils.unwrapObservable(indicators);
        if (self.qIndex < self.queueLength) {
            fnProcessNextCallback(self.qIndex, self.next);
        } else {
            self.d.resolve();
        }
    };
};

mvp.MVPIndicatorUpdater = function (updateUrl, fnCallbackData, fnCallbackError) {
    'use strict';
    var self = this;
    self.d = null;
    self.updateUrl = updateUrl;
    self.getFullURL = function () {
        return self.updateUrl + window.location.search.replace( "?", "&" );
    };
    self.fnCallbackData = fnCallbackData;
    self.fnCallbackError = fnCallbackError;
    self.numRetries = 0;
    self.maxRetries = 3;

    self.start = function () {
        self.d = $.Deferred();
        self.getIndicator();
    };

    self.getIndicator = function () {
        $.ajax({
            url: self.getFullURL(),
            dataType: 'json',
            success: self.processData,
            error: self.processError
        });
    };

    self.processData = function (data) {
        self.fnCallbackData(data);
        self.d.resolve();
    };

    self.processError = function (data) {
        self.numRetries ++;
        if (self.numRetries <= self.maxRetries) {
            self.getIndicator();
        } else {
            self.fnCallbackError();
            self.d.fail();
        }
    };

};
