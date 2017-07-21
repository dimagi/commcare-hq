/* globals ko, $ */

hqDefine("data_interfaces/js/case_rule_criteria.js", function() {

    var CaseRuleCriteria = function(initial, constants) {
        'use strict';
        var self = this;

        self.case_type = ko.observable();
        self.criteria = ko.observableArray();
        self.selected_case_filter_id = ko.observable();
        self.show_add_filter_warning = ko.observable(false);

        self.filter_on_server_modified = ko.computed(function() {
            var result = 'false';
            $.each(self.criteria(), function(index, value) {
                if(value.ko_template_id === 'case-modified-filter') {
                    result = 'true';
                }
            });
            return result;
        });

        self.server_modified_boundary = ko.computed(function() {
            var result = '';
            $.each(self.criteria(), function(index, value) {
                if(value.ko_template_id === 'case-modified-filter') {
                    result = value.days();
                }
            });
            return result;
        });

        self.custom_match_definitions = ko.computed(function() {
            var result = [];
            $.each(self.criteria(), function(index, value) {
                if(value.ko_template_id === 'custom-filter') {
                    result.push({
                        name: value.name() || '',
                    });
                }
            });
            return JSON.stringify(result);
        });

        self.property_match_definitions = ko.computed(function() {
            var result = [];
            $.each(self.criteria(), function(index, value) {
                if(value.ko_template_id === 'case-property-filter') {
                    result.push({
                        property_name: value.property_name() || '',
                        property_value: value.property_value() || '',
                        match_type: value.match_type() || '',
                    });
                } else if(value.ko_template_id === 'date-case-property-filter') {
                    result.push({
                        property_name: value.property_name() || '',
                        property_value: '0',
                        match_type: value.match_type() || '',
                    });
                } else if(value.ko_template_id === 'advanced-date-case-property-filter') {
                    var property_value = value.property_value();
                    if($.isNumeric(property_value) && value.plus_minus() === '-') {
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

        self.filter_on_closed_parent = ko.computed(function() {
            var result = 'false';
            $.each(self.criteria(), function(index, value) {
                if(value.ko_template_id === 'parent-closed-filter') {
                    result = 'true';
                }
            });
            return result;
        });

        self.get_ko_template_id = function(obj) {
            return obj.ko_template_id;
        };

        self.filter_already_added = function(ko_template_id) {
            for(var i = 0; i < self.criteria().length; i++) {
                if(self.criteria()[i].ko_template_id === ko_template_id) {
                    return true;
                }
            }

            return false;
        };

        self.add_filter = function() {
            var case_filter_id = self.selected_case_filter_id();
            if(case_filter_id === 'select-one') {
                return;
            }

            if(case_filter_id === 'case-modified-filter') {
                if(!self.filter_already_added(case_filter_id)) {
                    self.criteria.push(new NotModifiedSinceDefinition(case_filter_id));
                }
            } else if(
                case_filter_id === 'case-property-filter' ||
                case_filter_id === 'date-case-property-filter' ||
                case_filter_id === 'advanced-date-case-property-filter'
            ) {
                self.criteria.push(new MatchPropertyDefinition(case_filter_id));
            } else if(case_filter_id === 'parent-closed-filter') {
                if(!self.filter_already_added(case_filter_id)) {
                    self.criteria.push(new ClosedParentDefinition(case_filter_id));
                }
            } else if(case_filter_id === 'custom-filter') {
                self.criteria.push(new CustomMatchDefinition(case_filter_id));
            }
            self.selected_case_filter_id('select-one');
            self.show_add_filter_warning(false);
        };

        self.remove_filter = function() {
            self.criteria.remove(this);
        };

        self.load_initial = function() {
            var obj = null;
            if(initial.filter_on_server_modified !== 'false') {
                // check for not false in order to help prevent accidents in the future
                obj = new NotModifiedSinceDefinition('case-modified-filter');
                obj.days(initial.server_modified_boundary);
                self.criteria.push(obj);
            }

            $.each(initial.property_match_definitions, function(index, value) {
                if(
                    value.match_type === constants.MATCH_EQUAL ||
                    value.match_type === constants.MATCH_NOT_EQUAL ||
                    value.match_type === constants.MATCH_HAS_VALUE
                ) {
                    obj = new MatchPropertyDefinition('case-property-filter');
                    obj.property_name(value.property_name);
                    obj.property_value(value.property_value);
                    obj.match_type(value.match_type);
                    self.criteria.push(obj);
                } else if(
                    value.match_type === constants.MATCH_DAYS_BEFORE ||
                    value.match_type === constants.MATCH_DAYS_AFTER
                ) {
                    var days = Number.parseInt(value.property_value);
                    if(days === 0) {
                        obj = new MatchPropertyDefinition('date-case-property-filter');
                        obj.property_value(value.property_value);
                    } else {
                        obj = new MatchPropertyDefinition('advanced-date-case-property-filter');
                        obj.plus_minus((days > 0) ? '+' : '-');
                        obj.property_value(Math.abs(days).toString());
                    }
                    obj.property_name(value.property_name);
                    obj.match_type(value.match_type);
                    self.criteria.push(obj);
                }
            });

            $.each(initial.custom_match_definitions, function(index, value) {
                obj = new CustomMatchDefinition('custom-filter');
                obj.name(value.name);
                self.criteria.push(obj);
            });

            if(initial.filter_on_closed_parent !== 'false') {
                // check for not false in order to help prevent accidents in the future
                self.criteria.push(new ClosedParentDefinition('parent-closed-filter'));
            }
        };
    };

    var NotModifiedSinceDefinition = function(ko_template_id) {
        'use strict';
        var self = this;
        self.ko_template_id = ko_template_id;

        // This model does not match a Django model; the `days` are stored as the `server_modified_boundary` on the rule
        self.days = ko.observable();
    };

    var MatchPropertyDefinition = function(ko_template_id) {
        'use strict';
        var self = this;
        self.ko_template_id = ko_template_id;
        self.plus_minus = ko.observable();

        // This model matches the Django model with the same name
        self.property_name = ko.observable();
        self.property_value = ko.observable();
        self.match_type = ko.observable();
    };

    var CustomMatchDefinition = function(ko_template_id) {
        'use strict';
        var self = this;
        self.ko_template_id = ko_template_id;

        // This model matches the Django model with the same name
        self.name = ko.observable();
    };

    var ClosedParentDefinition = function(ko_template_id) {
        'use strict';
        var self = this;
        self.ko_template_id = ko_template_id;

        // This model matches the Django model with the same name
    };

    var criteria_model = null;

    $(function() {
        criteria_model = new CaseRuleCriteria(
            hqImport("hqwebapp/js/initial_page_data.js").get('criteria_initial'),
            hqImport("hqwebapp/js/initial_page_data.js").get('criteria_constants')
        );
        $('#rule-criteria').koApplyBindings(criteria_model);
        criteria_model.load_initial();
    });

    return {
        get_criteria_model: function() {return criteria_model;},
    };

});
