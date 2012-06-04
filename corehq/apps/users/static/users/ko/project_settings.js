var HQTimezoneHandler = function (o) {
    'use strict';
    var self = this;
    self.override_tz = ko.observable(o.override);
    self.form_is_ready = ko.observable(false);

    self.updateForm = function(data, event) {
        self.form_is_ready(true);
    };
};