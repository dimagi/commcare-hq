hqDefine("data_interfaces/js/case_rule_actions", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    initialPageData
) {
    var caseRuleActions = function (initial) {
        'use strict';
        var self = {};

        self.actions = ko.observableArray();

        self.getKoTemplateId = function (obj) {
            if (obj instanceof closeCaseDefinition) {
                return 'close-case-action';
            } else if (obj instanceof updatePropertyDefinition) {
                return 'update-case-property-action';
            } else if (obj instanceof customActionDefinition) {
                return 'custom-action';
            }
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
                if (value instanceof closeCaseDefinition) {
                    result = 'true';
                }
            });
            return result;
        });

        self.propertiesToUpdate = ko.computed(function () {
            var result = [];
            $.each(self.actions(), function (index, value) {
                if (value instanceof updatePropertyDefinition) {
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
                if (value instanceof customActionDefinition) {
                    result.push({
                        name: value.name() || '',
                    });
                }
            });
            return JSON.stringify(result);
        });

        self.actionAlreadyAdded = function (jsClass) {
            for (var i = 0; i < self.actions().length; i++) {
                if (self.actions()[i] instanceof jsClass) {
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

            if (jsClass === closeCaseDefinition && self.actionAlreadyAdded(closeCaseDefinition)) {
                return;
            }

            self.actions.push(jsClass());
        };

        self.removeAction = function () {
            self.actions.remove(this);
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
        return self;
    };

    var closeCaseDefinition = function () {
        'use strict';
        var self = {};

        // This model matches up with the Django UpdateCaseDefinition.close_case model attribute
        return self;
    };

    var updatePropertyDefinition = function () {
        'use strict';
        var self = {};

        // This model matches up with one instance in the Django UpdateCaseDefinition.properties_to_update model attribute
        self.name = ko.observable();
        self.value_type = ko.observable();
        self.value = ko.observable();
        return self;
    };

    var customActionDefinition = function () {
        'use strict';
        var self = {};

        // This model matches the Django model with the same name
        self.name = ko.observable();
        return self;
    };

    var actionsModel = null;

    $(function () {
        actionsModel = caseRuleActions(initialPageData.get('actions_initial'));
        $('#rule-actions').koApplyBindings(actionsModel);
        actionsModel.loadInitial();
    });

    return {
        get_actions_model: function () {return actionsModel;},
    };

});
