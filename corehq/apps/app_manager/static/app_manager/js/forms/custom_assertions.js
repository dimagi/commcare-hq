/* globals ko */
hqDefine('app_manager/js/forms/custom_assertions', function () {
    'use strict';

    var customAssertion = function (test, text) {
        var self = {};
        self.test = ko.observable(test || '');
        self.text = ko.observable(text || '');
        return self;
    };

    var customAssertions = function () {
        var self = {};
        self.customAssertions = ko.observableArray();

        self.mapping = {
            customAssertions: {
                create: function (options) {
                    return customAssertion(options.data.test, options.data.text);
                },
            },
        };

        self.wrap = function (assertions) {
            return ko.mapping.fromJS(assertions, self.mapping, self);
        };

        self.unwrap = function () {
            return ko.mapping.toJS(self);
        };

        self.addAssertion = function (assertion) {
            assertion = assertion || {test: null, text: null};
            self.customAssertions.push(
                customAssertion(assertion.test, assertion.text)
            );
        };

        self.removeAssertion = function (assertion) {
            self.customAssertions.remove(assertion);
        };

        self.serializedCustomAssertions = ko.computed(function () {
            return JSON.stringify(self.unwrap().customAssertions);
        });

        return self;
    };

    return customAssertions();
});
