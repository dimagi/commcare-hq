hqDefine("reports/js/filters/case_list_explorer", ['jquery', 'underscore', 'knockout'], function($, _, ko) {
    'use strict';

    var applySuggestions = function(allSuggestions){
        // Adds the required properties to filter the case type autocomplete dropdowns
        var self = this;
        self.currentCaseType = ko.observable('');
        $('#report_filter_case_type').on('change', function(e){
            self.currentCaseType(e.val);
        });

        self.suggestedProperties = ko.computed(function(){
            if (self.currentCaseType() === ''){
                return allSuggestions;
            }
            return _.filter(allSuggestions, function(prop){
                return prop['case_type'] === self.currentCaseType() || prop['case_type'] === null;
            });
        });
    };

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
            var value = _.find($parent.allSuggestions, function(prop){
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
        var self = {
            allSuggestions: allCaseProperties,
        };
        applySuggestions.call(self, allCaseProperties);

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

            return JSON.stringify(
                _.map(self.properties(), function(property){
                    var pertinent_props = {name: property.name(), label: property.label()};
                    if (property.hidden()){
                        pertinent_props.hidden = property.hidden();
                    }
                    if (property.meta_type()){
                        pertinent_props.meta_type = property.meta_type();
                    }
                    return pertinent_props;
                })
            );
        });

        return self;
    };

    var caseSearchXpathViewModel = function(allSuggestions){
        var self = {};
        applySuggestions.call(self, allSuggestions);
        return self;
    };

    return {
        casePropertyColumns: casePropertyColumnsViewModel,
        caseSearchXpath: caseSearchXpathViewModel,
    };
});
