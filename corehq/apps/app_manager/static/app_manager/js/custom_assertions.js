hqDefine('app_manager/js/custom_assertions', function () {
    'use strict';
    var initialPageData = hqImport("hqwebapp/js/initial_page_data").get;

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
            let ret = ko.mapping.fromJS(assertions, self.mapping, self);

            // after initialization, fire change event so save button works
            self.customAssertions.subscribe(function () {
                $("#custom-assertions input[name='custom_assertions']").change();
            });

            return ret;
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

    $(function () {
        if (hqImport('hqwebapp/js/toggles').toggleEnabled('CUSTOM_ASSERTIONS')) {
            var assertions = customAssertions().wrap({
                'customAssertions': initialPageData('custom_assertions'),
            });
            $('#custom-assertions').koApplyBindings(assertions);
        }
    });

});
