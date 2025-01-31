hqDefine('app_manager/js/custom_assertions', [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/toggles',
], function (
    $,
    ko,
    initialPageData,
    toggles,
) {
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
                customAssertion(assertion.test, assertion.text),
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
        if (toggles.toggleEnabled('CUSTOM_ASSERTIONS')) {
            const $container = $('#custom-assertions');
            if ($container.length) {
                var assertions = customAssertions().wrap({
                    'customAssertions': initialPageData.get('custom_assertions'),
                });
                $container.koApplyBindings(assertions);
            }
        }
    });

});
