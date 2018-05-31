var suggestions = function(){
    // Adds the required properties to filter the case type autocomplete dropdowns
    var self = this;
    self.currentCaseType = ko.observable('');
    $('#report_filter_case_type').on('change', function(e){
        self.currentCaseType(e.val);
    });

    self.suggestedProperties = ko.computed(function(){
        if (self.currentCaseType() === ''){
            return self.allSuggestions;
        }
        return _.filter(self.allSuggestions, function(prop){
            return prop['case_type'] === self.currentCaseType() || prop['case_type'] === null;
        });
    });
};

hqDefine("reports/js/filters/case_list_explorer", ['jQuery', 'underscore', 'knockout'], function($, _, ko) {
    'use strict';

    var Property = function ($parent, name, label, editable, hidden) {
        var self = {};
        self.name = ko.observable(name).trimmed();

        self.label = ko.observable(label || name).trimmed();

        self.name.subscribe(function(newValue){
            // Set the label value to the value of the name if it isn't otherwise set
            if (!self.label() && newValue !== 'undefined'){ // atwho sometimes sets the value to the string 'undefined'
                var val = newValue.replace('@', '').replace(/_/g, ' ').replace(/\w\S*/g, function(txt){
                    return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
                });
                self.label(val);
            }
        });

        self.meta_type = ko.computed(function(){
            var value = _.find($parent.allCaseProperties, function(prop){
                return prop.name === self.name();
            });
            if (value){
                return value.meta_type;
            }
            return null;
        });
        self.editable = ko.observable(editable === undefined ? true : editable);
        self.hidden = ko.observable(hidden || false);

        return self;
    };

    var casePropertyColumnsViewModel = function(initialColumns, allCaseProperties) {
        var self = this;

        self.allSuggestions = allCaseProperties;
        suggestions.apply(self);

        self.properties = ko.observableArray();
        for (var i = 0; i < initialColumns.length; i++){
            var initialColumn = initialColumns[i];
            self.properties.push(Property(self, initialColumn.name, initialColumn.label, initialColumn.editable, initialColumn.hidden));
        }

        self.addProperty = function () {
            self.properties.push(Property(self, '', ''));
        };

        self.removeProperty = function (property) {
            self.properties.remove(property);
            $('#fieldset_explorer_columns').trigger('change');
        };

        self.allProperties = ko.computed(function(){
            return JSON.stringify(ko.toJS(self.properties()));
        });

        return self;
    };

    var caseSearchXpathViewModel = function(allSuggestions){
        var self = this;
        self.allSuggestions = allSuggestions;
        suggestions.apply(self);
        return self;
    };

    return {
        casePropertyColumns: casePropertyColumnsViewModel,
        caseSearchXpath: caseSearchXpathViewModel,
    };
});
