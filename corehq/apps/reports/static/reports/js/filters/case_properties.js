hqDefine("reports/js/filters/case_properties", ['knockout'], function(ko) {
    'use strict';

    var Property = function (name, label, is_default) {
        var self = this;
        self.name = ko.observable(name).trimmed();
        self.label = ko.observable(label).trimmed();
        self.is_default = ko.observable(is_default || false);
    };

    var CasePropertiesFilterViewModel = function(initialProperties) {
        var self = this;

        self.properties = ko.observableArray();
        for (var i = 0; i < initialProperties.length; i++){
            var initialProperty = initialProperties[i];
            self.properties.push(new Property(initialProperty.name, initialProperty.label, initialProperty.is_default));
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
    return {model: CasePropertiesFilterViewModel};
});
