var SuggestedCaseTypes = function(){
    // Adds the required properties to filter the case type autocomplete dropdowns
    var self = this;
    self.currentCaseType = ko.observable('');
    $('#report_filter_case_type').on('change', function(e){
        self.currentCaseType(e.val);
    });

    self.suggestedProperties = ko.computed(function(){
        if (self.currentCaseType() === ''){
            return self.allCaseProperties;
        }
        return _.filter(self.allCaseProperties, function(prop){
            return prop['case_type'] === self.currentCaseType() || prop['case_type'] === null;
        });
    });
};

hqDefine("reports/js/filters/case_properties", ['jQuery', 'underscore', 'knockout'], function($, _, ko) {
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

    var CasePropertyColumnsViewModel = function(initialColumns, allCaseProperties) {
        var self = this;

        self.allCaseProperties = allCaseProperties;
        SuggestedCaseTypes.apply(self);

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
        };

        self.allProperties = ko.computed(function(){
            return JSON.stringify(ko.toJS(self.properties()));
        });

        return self;
    };
    return {model: CasePropertyColumnsViewModel};
});


hqDefine("reports/js/filters/case_search_xpath", function() {
    var CaseSearchXpathViewModel = function(allCaseProperties){
        var self = this;
        self.allCaseProperties = allCaseProperties;
        SuggestedCaseTypes.apply(self);
        return self;
    };

    return {model: CaseSearchXpathViewModel};
});


ko.bindingHandlers.xPathAutocomplete = {
    init: function(element) {
        var $element = $(element);
        if (!$element.atwho) {
            throw new Error("The typeahead binding requires Atwho.js and Caret.js");
        }

        hqImport('hqwebapp/js/atwho').init($element, {
            atwhoOptions: {
                displayTpl: '<li><span class="label label-default">${case_type}</span> ${name}</li>',
                callbacks: {},
            },
            afterInsert: function() {
                $element.trigger('textchange');
            },
            replaceValue: false,
        });

        $element.on("textchange", function() {
            if ($element.val()) {
                $element.change();
            }
        });
    },

    update: function(element, valueAccessor) {
        $(element).atwho('load', '', ko.utils.unwrapObservable(valueAccessor()));
    },
};


ko.bindingHandlers.explorerColumnsAutocomplete = {
    init: function(element) {
        var $element = $(element);
        if (!$element.atwho) {
            throw new Error("The typeahead binding requires Atwho.js and Caret.js");
        }

        hqImport('hqwebapp/js/atwho').init($element, {
            atwhoOptions: {
                displayTpl: function(item){
                    if (item.case_type){
                        return '<li><span class="label label-default">${case_type}</span> ${name}</li>';
                    }
                    return '<li><span class="label label-primary">${meta_type}</span> ${name}</li>';
                },
            },
            afterInsert: function() {
                $element.trigger('textchange');
            },
        });

        $element.on("textchange", function() {
            if ($element.val()) {
                $element.change();
            }
        });
    },

    update: function(element, valueAccessor) {
        $(element).atwho('load', '', ko.utils.unwrapObservable(valueAccessor()));
    },
};
