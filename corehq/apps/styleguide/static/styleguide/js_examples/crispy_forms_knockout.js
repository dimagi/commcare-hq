$(function () {
    'use strict';

    let ExampleFormModel = function () {
        let self = {};
        self.fullName = ko.observable();
        self.areas = ko.observableArray([
            gettext('Forms'), gettext('Cases'), gettext('Reports'), gettext('App Builder'),
        ]);
        self.area = ko.observable();
        self.includeMessage = ko.observable(false);
        self.message = ko.observable();
        self.alertText = ko.observable();

        self.onFormSubmit = function () {
            // an ajax call would likely happen here in the real world

            self.alertText(gettext("Thank you, " + self.fullName() + ", for your submission!"));
            self._resetForm();
        };

        self.cancelSubmission = function () {
            self.alertText(gettext("Submission has been cancelled."));
            self._resetForm();
        };

        self._resetForm = function () {
            self.fullName('');
            self.area(undefined);
            self.includeMessage(false);
            self.message('');

            // clear alert text after 2 sec
            setTimeout(function () {
                self.alertText('');
            }, 2000);
        };
        return self;
    };
    $("#ko-example-crispy-form").koApplyBindings(ExampleFormModel());
});
