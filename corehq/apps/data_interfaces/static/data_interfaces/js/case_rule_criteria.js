hqDefine("data_interfaces/js/case_rule_criteria", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
], function ($, ko, initialPageData) {

    var caseRuleCriteria = function (initial, constants) {
        'use strict';
        var self = {};

        self.constants = constants;
        self.caseType = ko.observable(initial.case_type);
        self.criteria = ko.observableArray();

        self.filterOnServerModified = ko.computed(function () {
            var result = 'false';
            $.each(self.criteria(), function (index, value) {
                if (value.koTemplateId === 'case-modified-filter') {
                    result = 'true';
                }
            });
            return result;
        });

        self.serverModifiedBoundary = ko.computed(function () {
            var result = '';
            $.each(self.criteria(), function (index, value) {
                if (value.koTemplateId === 'case-modified-filter') {
                    result = value.days();
                }
            });
            return result;
        });

        self.customMatchDefinitions = ko.computed(function () {
            var result = [];
            $.each(self.criteria(), function (index, value) {
                if (value.koTemplateId === 'custom-filter') {
                    result.push({
                        name: value.name() || '',
                    });
                }
            });
            return JSON.stringify(result);
        });

        self.propertyMatchDefinitions = ko.computed(function () {
            var result = [];
            $.each(self.criteria(), function (index, value) {
                if (value.koTemplateId === 'case-property-filter') {
                    result.push({
                        property_name: value.property_name() || '',
                        property_value: value.property_value() || '',
                        match_type: value.match_type() || '',
                    });
                } else if (value.koTemplateId === 'date-case-property-filter') {
                    result.push({
                        property_name: value.property_name() || '',
                        property_value: '0',
                        match_type: value.match_type() || '',
                    });
                } else if (value.koTemplateId === 'advanced-date-case-property-filter') {
                    var property_value = value.property_value();
                    if ($.isNumeric(property_value) && value.plus_minus() === '-') {
                        // The value of plus_minus tells us if we should negate the number
                        // given in property_value(). We only attempt to do this if it
                        // actually represents a number. If it doesn't, let the django
                        // validation catch it.
                        property_value = -1 * Number.parseInt(property_value);
                        property_value = property_value.toString();
                    }
                    result.push({
                        property_name: value.property_name() || '',
                        property_value: property_value || '',
                        match_type: value.match_type() || '',
                    });
                }
            });
            return JSON.stringify(result);
        });

        self.filterOnClosedParent = ko.computed(function () {
            var result = 'false';
            $.each(self.criteria(), function (index, value) {
                if (value.koTemplateId === 'parent-closed-filter') {
                    result = 'true';
                }
            });
            return result;
        });

        self.getKoTemplateId = function (obj) {
            return obj.koTemplateId;
        };

        self.filterAlreadyAdded = function (koTemplateId) {
            for (var i = 0; i < self.criteria().length; i++) {
                if (self.criteria()[i].koTemplateId === koTemplateId) {
                    return true;
                }
            }

            return false;
        };

        self.disableCriteriaField = function () {
            if (initialPageData.get('read_only_mode')) {
                $('.main-form :input').prop('disabled', true);
            }
        };

        self.addFilter = function (caseFilterId) {
            if (caseFilterId === 'select-one') {
                return;
            }

            if (caseFilterId === 'case-modified-filter') {
                if (!self.filterAlreadyAdded(caseFilterId)) {
                    self.criteria.push(notModifiedSinceDefinition(caseFilterId));
                }
            } else if (
                caseFilterId === 'case-property-filter' ||
                caseFilterId === 'date-case-property-filter' ||
                caseFilterId === 'advanced-date-case-property-filter'
            ) {
                self.criteria.push(matchPropertyDefinition(caseFilterId));
            } else if (caseFilterId === 'parent-closed-filter') {
                if (!self.filterAlreadyAdded(caseFilterId)) {
                    self.criteria.push(closedParentDefinition(caseFilterId));
                }
            } else if (caseFilterId === 'custom-filter') {
                self.criteria.push(customMatchDefinition(caseFilterId));
            }
        };

        self.removeFilter = function () {
            self.criteria.remove(this);
        };

        self.loadInitial = function () {
            var obj = null;
            if (initial.filter_on_server_modified !== 'false') {
                // check for not false in order to help prevent accidents in the future
                obj = notModifiedSinceDefinition('case-modified-filter');
                obj.days(initial.server_modified_boundary);
                self.criteria.push(obj);
            }
            $.each(initial.property_match_definitions, function (index, value) {
                if (
                    value.match_type === constants.MATCH_EQUAL ||
                    value.match_type === constants.MATCH_NOT_EQUAL ||
                    value.match_type === constants.MATCH_REGEX ||
                    value.match_type === constants.MATCH_HAS_VALUE ||
                    value.match_type === constants.MATCH_HAS_NO_VALUE
                ) {
                    obj = matchPropertyDefinition('case-property-filter');
                    obj.property_name(value.property_name);
                    obj.property_value(value.property_value);
                    obj.match_type(value.match_type);
                    self.criteria.push(obj);
                } else if (
                    value.match_type === constants.MATCH_DAYS_BEFORE ||
                    value.match_type === constants.MATCH_DAYS_AFTER
                ) {
                    var days = Number.parseInt(value.property_value);
                    if (days === 0) {
                        obj = matchPropertyDefinition('date-case-property-filter');
                        obj.property_value(value.property_value);
                    } else {
                        obj = matchPropertyDefinition('advanced-date-case-property-filter');
                        obj.plus_minus((days > 0) ? '+' : '-');
                        obj.property_value(Math.abs(days).toString());
                    }
                    obj.property_name(value.property_name);
                    obj.match_type(value.match_type);
                    self.criteria.push(obj);
                }
            });

            $.each(initial.custom_match_definitions, function (index, value) {
                obj = customMatchDefinition('custom-filter');
                obj.name(value.name);
                self.criteria.push(obj);
            });

            if (initial.filter_on_closed_parent !== 'false') {
                // check for not false in order to help prevent accidents in the future
                self.criteria.push(closedParentDefinition('parent-closed-filter'));
            }
        };

        self.setScheduleTabVisibility = function () {
            if (self.ruleTabValid()) {
                $("#schedule-nav").removeClass("hidden");
            }
        };

        self.ruleTabValid = ko.computed(function () {
            return !_.isEmpty(self.caseType());
        });

        self.handleRuleNavContinue = function () {
            $("#schedule-nav").removeClass("hidden");
            $('#schedule-nav').find('a').trigger('click');
        };
        return self;
    };

    var notModifiedSinceDefinition = function (koTemplateId) {
        'use strict';
        var self = {};
        self.koTemplateId = koTemplateId;

        // This model does not match a Django model; the `days` are stored as the `server_modified_boundary` on the rule
        self.days = ko.observable();
        return self;
    };

    var matchPropertyDefinition = function (koTemplateId) {
        'use strict';
        var self = {};
        self.koTemplateId = koTemplateId;
        self.plus_minus = ko.observable();

        // This model matches the Django model with the same name
        self.property_name = ko.observable();
        self.property_value = ko.observable();
        self.match_type = ko.observable();

        self.showPropertyValueInput = ko.computed(function () {
            return (
                self.match_type() !== criteriaModel.constants.MATCH_HAS_VALUE &&
                self.match_type() !== criteriaModel.constants.MATCH_HAS_NO_VALUE
            );
        });
        return self;
    };

    var customMatchDefinition = function (koTemplateId) {
        'use strict';
        var self = {};
        self.koTemplateId = koTemplateId;

        // This model matches the Django model with the same name
        self.name = ko.observable();
        return self;
    };

    var closedParentDefinition = function (koTemplateId) {
        'use strict';
        var self = {};
        self.koTemplateId = koTemplateId;

        // This model matches the Django model with the same name
        return self;
    };

    var criteriaModel = null;

    $(function () {
        criteriaModel = caseRuleCriteria(
            initialPageData.get('criteria_initial'),
            initialPageData.get('criteria_constants')
        );
        // setup tab
        criteriaModel.setScheduleTabVisibility();
        $('#rule-criteria-panel').koApplyBindings(criteriaModel);
        criteriaModel.loadInitial();
    });

    return {
        get_criteria_model: function () {return criteriaModel;},
    };

});
