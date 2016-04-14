/* globals hqDefine, ko */

hqDefine('domain/js/case-search-config.js', function () {
    'use strict';

    var module = {};

    module.CaseSearchConfig = function (options) {
        var self = this;
        var initialValues = options.values;
        self.caseTypes = options.caseTypes;

        var viewModel = {
            toggleEnabled: ko.observable(initialValues.enabled)
        };

//        viewModel.toggleEnabled.subscribe(function (newValue) {
//            if (newValue === true) {
//                $('#fuzzies_div').removeClass('text-muted');
//            } else {
//                $('#fuzzies_div').addClass('text-muted');
//            }
//        });

        return viewModel;
    };

    return module;
});
