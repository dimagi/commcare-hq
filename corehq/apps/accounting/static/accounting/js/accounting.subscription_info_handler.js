var SubscriptionInfoHandler = function () {
    'use strict';
    var self = this;

    self.domain = new AsyncSelect2Handler('domain');

    self.init = function () {
        self.domain.init();
    };
};
