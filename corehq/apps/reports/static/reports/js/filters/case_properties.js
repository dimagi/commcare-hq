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

        self.suggestedProperties = ko.observableArray(allCaseProperties['child']);

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


ko.bindingHandlers.casePropertyAutocomplete = {
    /*
     * Strip "attachment:" prefix and show icon for attachment properties.
     * Replace any spaces in free text with underscores.
     */
    init: function (element, valueAccessor) {
        $(element).on('textchange', function() {
            var $el = $(this);
            if ($el.val().match(/\s/)) {
                var pos = $el.caret('pos');
                $el.val($el.val().replace(/\s/g, '_'));
                $el.caret('pos', pos);
            }
        });
        ko.bindingHandlers.autocompleteAtwho.init(element, valueAccessor);
    },
    update: function (element, valueAccessor, allBindingsAccessor) {
        function wrappedValueAccessor() {
            return _.map(ko.unwrap(valueAccessor()), function(value) {
                if (value.indexOf("attachment:") === 0) {
                    var text = value.substring(11),
                        html = '<i class="fa fa-paperclip"></i> ' + text;
                    return {name: text, content: html};
                }
                return {name: value, content: value};
            });
        }
        ko.bindingHandlers.autocompleteAtwho.update(element, wrappedValueAccessor, allBindingsAccessor);
    },
};
