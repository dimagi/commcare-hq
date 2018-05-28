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
            return prop['case_type'] == self.currentCaseType() || prop['case_type'] == null;
        });
    });
};


hqDefine("reports/js/filters/case_properties", ['jQuery', 'underscore', 'knockout'], function($, _, ko) {
    'use strict';

    var Property = function (name, label, editable, hidden) {
        var self = this;
        self.name = ko.observable(name).trimmed();
        self.label = ko.observable(label).trimmed();
        self.editable = ko.observable(editable === undefined ? true : editable);
        self.hidden = ko.observable(hidden || false);
    };

    var CasePropertyColumnsViewModel = function(initialColumns, allCaseProperties) {
        var self = this;

        self.allCaseProperties = allCaseProperties;
        SuggestedCaseTypes.apply(self);

        self.properties = ko.observableArray();
        for (var i = 0; i < initialColumns.length; i++){
            var initialColumn = initialColumns[i];
            self.properties.push(new Property(
                initialColumn.name, initialColumn.label, initialColumn.editable, initialColumn.hidden
            ));
        }

        self.addProperty = function () {
            self.properties.push(new Property('', ''));
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


hqDefine("reports/js/filters/case_search_xpath", ['knockout'], function(ko) {
    var CaseSearchXpathViewModel = function(allCaseProperties){
        var self = this;
        self.allCaseProperties = allCaseProperties;
        SuggestedCaseTypes.apply(self);
        return self;
    };

    return {model: CaseSearchXpathViewModel};
});


ko.bindingHandlers.xPathAutocomplete = {
    init: function(element, valueAccessor) {
        var $element = $(element);
        if (!$element.atwho) {
            throw new Error("The typeahead binding requires Atwho.js and Caret.js");
        }

        hqImport('hqwebapp/js/atwho').init($element, {
            atwhoOptions: {
                displayTpl: '<li><span class=\"badge\">${case_type}</span> ${name}</li>',
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

    update: function(element, valueAccessor, allBindings) {
        $(element).atwho('load', '', ko.utils.unwrapObservable(valueAccessor()));
    },
};


ko.bindingHandlers.explorerColumnsAutocomplete = {
    init: function(element, valueAccessor) {
        var $element = $(element);
        if (!$element.atwho) {
            throw new Error("The typeahead binding requires Atwho.js and Caret.js");
        }

        hqImport('hqwebapp/js/atwho').init($element, {
            atwhoOptions: {
                displayTpl: '<li><span class=\"badge\">${case_type}</span> ${name}</li>',
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

    update: function(element, valueAccessor, allBindings) {
        $(element).atwho('load', '', ko.utils.unwrapObservable(valueAccessor()));
    },
};
