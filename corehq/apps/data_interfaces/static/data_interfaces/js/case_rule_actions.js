hqDefine("data_interfaces/js/case_rule_actions", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    initialPageData
) {
    var CaseRuleActions = function (initial, caseTypeObservable) {
        'use strict';
        var self = {};

        self.actions = ko.observableArray();

        // For the sake of passing to case property input component
        self.caseType = caseTypeObservable;

        self.getKoTemplateId = function (obj) {
            return obj.template_id;
        };

        self.getJsClass = function (templateId) {
            if (templateId === 'close-case-action') {
                return closeCaseDefinition;
            } else if (templateId === 'update-case-property-action') {
                return updatePropertyDefinition;
            } else if (templateId === 'custom-action') {
                return customActionDefinition;
            }
        };

        self.closeCase = ko.computed(function () {
            var result = 'false';
            $.each(self.actions(), function (index, value) {
                if (value.template_id === 'close-case-action') {
                    result = 'true';
                }
            });
            return result;
        });

        self.propertiesToUpdate = ko.computed(function () {
            var result = [];
            $.each(self.actions(), function (index, value) {
                if (value.template_id === 'update-case-property-action') {
                    result.push({
                        name: value.name() || '',
                        value_type: value.value_type() || '',
                        value: value.value() || '',
                    });
                }
            });
            return JSON.stringify(result);
        });

        self.customActionDefinitions = ko.computed(function () {
            var result = [];
            $.each(self.actions(), function (index, value) {
                if (value.template_id === 'custom-action') {
                    result.push({
                        name: value.name() || '',
                    });
                }
            });
            return JSON.stringify(result);
        });

        self.actionAlreadyAdded = function (templateId) {
            for (var i = 0; i < self.actions().length; i++) {
                if (self.actions()[i].template_id === templateId) {
                    return true;
                }
            }

            return false;
        };

        self.addAction = function (templateId) {
            if (templateId === 'select-one') {
                return;
            }
            var jsClass = self.getJsClass(templateId);

            if (jsClass === closeCaseDefinition && self.actionAlreadyAdded('close-case-action')) {
                return;
            }

            self.actions.push(jsClass());
        };

        self.removeAction = function () {
            self.actions.remove(this);
        };

        self.disableActionField = function () {
            if (initialPageData.get('read_only_mode')) {
                $('.main-form :input').prop('disabled', true);
            }
        };

        self.loadInitial = function () {
            if (initial.close_case === 'true') {
                var obj = closeCaseDefinition();
                self.actions.push(obj);
            }

            $.each(initial.properties_to_update, function (index, value) {
                var obj = updatePropertyDefinition();
                obj.name(value.name);
                obj.value_type(value.value_type);
                obj.value(value.value);
                self.actions.push(obj);
            });

            $.each(initial.custom_action_definitions, function (index, value) {
                var obj = customActionDefinition();
                obj.name(value.name);
                self.actions.push(obj);
            });
        };

        self.loadInitial();
        return self;
    };

    var closeCaseDefinition = function () {
        // This model matches up with the Django UpdateCaseDefinition.close_case model attribute
        return {
            template_id: 'close-case-action',
        };
    };

    var updatePropertyDefinition = function () {
        'use strict';
        var self = {};

        // This model matches up with one instance in the Django UpdateCaseDefinition.properties_to_update model attribute
        self.name = ko.observable();
        self.template_id = 'update-case-property-action';
        self.value_type = ko.observable();
        self.value = ko.observable();
        return self;
    };

    var customActionDefinition = function () {
        'use strict';
        var self = {};

        // This model matches the Django model with the same name
        self.name = ko.observable();
        self.template_id = 'custom-action';
        return self;
    };

    return CaseRuleActions;
});
