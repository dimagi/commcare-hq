/* globals ko */

var CaseRule = function() {
    'use strict';
    var self = this;

    self.name = ko.observable();
    self.case_type = ko.observable();
    self.criteria = ko.observableArray();
    self.actions = ko.observableArray();
    self.selected_case_filter_id = ko.observable();

    self.getKoTempateId = function(obj) {
        return obj.ko_template_id;
    }

    self.filterAlreadyAdded = function(ko_template_id) {
        for(var i = 0; i < self.criteria().length; i++) {
            if(self.criteria()[i].ko_template_id == ko_template_id) {
                return true;
            }
        }

        return false;
    }

    self.addFilter = function() {
        var case_filter_id = self.selected_case_filter_id()

        if(case_filter_id == 'case-modified-filter') {
            if(!self.filterAlreadyAdded(case_filter_id)) {
                self.criteria.push(new NotModifiedSinceDefinition(case_filter_id));
            }
        } else if(
            case_filter_id == 'case-property-filter' ||
            case_filter_id == 'date-case-property-filter' ||
            case_filter_id == 'advanced-date-case-property-filter'
        ) {
            self.criteria.push(new MatchPropertyDefinition(case_filter_id));
        } else if(case_filter_id == 'parent-closed-filter') {
            if(!self.filterAlreadyAdded(case_filter_id)) {
                self.criteria.push(new ClosedParentDefinition(case_filter_id));
            }
        } else if(case_filter_id == 'custom-filter') {
            self.criteria.push(new CustomMatchDefinition(case_filter_id));
        } 
    };

    self.removeFilter = function() {
        self.criteria.remove(this);
    };
};

var NotModifiedSinceDefinition = function(ko_template_id) {
    'use strict';
    var self = this;

    // This model does not match a Django model; the `days` are stored as the `server_modified_boundary` on the rule
    self.ko_template_id = ko_template_id;
    self.days = ko.observable();
};

var MatchPropertyDefinition = function(ko_template_id) {
    'use strict';
    var self = this;

    // This model matches the Django model with the same name
    self.ko_template_id = ko_template_id;
    self.property_name = ko.observable();
    self.property_value = ko.observable();
    self.match_type = ko.observable();
};

var CustomMatchDefinition = function(ko_template_id) {
    'use strict';
    var self = this;

    // This model matches the Django model with the same name
    self.ko_template_id = ko_template_id;
    self.name = ko.observable();
};

var ClosedParentDefinition = function(ko_template_id) {
    'use strict';
    var self = this;

    // This model matches the Django model with the same name
    self.ko_template_id = ko_template_id;
};
