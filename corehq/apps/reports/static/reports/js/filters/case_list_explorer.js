hqDefine("reports/js/filters/case_properties", ['knockout'], function(ko) {
    'use strict';

    var Property = function (name, label, is_default) {
        var self = this;
        self.name = ko.observable(name).trimmed();
        self.label = ko.observable(label).trimmed();
        self.is_default = ko.observable(is_default || false);
    };

    var CasePropertyColumnsViewModel = function(initialColumns, allCaseProperties) {
        var self = this;

        self.suggestedProperties = ko.observableArray(allCaseProperties);

        self.properties = ko.observableArray();
        for (var i = 0; i < initialColumns.length; i++){
            var initialColumn = initialColumns[i];
            self.properties.push(new Property(initialColumn.name, initialColumn.label, initialColumn.is_default));
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
        self.suggestedProperties = ko.observableArray(allCaseProperties);
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
                'displayTpl': '<li><span class=\"badge\">${caseType}</span> ${name}</li>',
                'callbacks': {},
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
