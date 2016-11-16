(function ($, _) {
    var CaseProperty = function (data) {
        this.name = ko.observable(data.name);
        this.type = ko.observable(data.type);
        this.description = ko.observable(data.description);
    };

    var CaseType = function (name) {
        var self = this;
        self.name = ko.observable(name);
        self.properties = ko.observableArray();

        self.init = function (properties) {
            _.each(properties, function (property) {
                self.properties.push(new CaseProperty(property));
            });
        };
    };

    var DataDictionaryModel = function (dataUrl) {
        var self = this;
        self.caseTypes = ko.observableArray();
        self.activeCaseType = ko.observable();

        self.init = function () {
            $.getJSON(dataUrl)
            .done(function (data) {
                _.each(data.properties, function (property) {
                    var caseType = new CaseType(property.type);
                    caseType.init(property.properties);
                    self.caseTypes.push(caseType);
                });
                self.activeCaseType(self.caseTypes()[0].name());
            });
        };

        this.activeCaseTypeData = ko.computed(function () {
            var caseTypes = self.caseTypes();
            if (caseTypes.length) {
                var caseType = _.find(caseTypes, function (prop) {
                    return prop.name() === self.activeCaseType();
                });
                if (caseType) {
                    return caseType.properties();
                }
            }
            return [];
        }, this);

        this.goToCaseType = function (caseType) {
            self.activeCaseType(caseType);
        };
    };

    $.fn.initializeDataDictionary = function (dataUrl) {
        var viewModel = new DataDictionaryModel(dataUrl);
        viewModel.init();
        $(this).koApplyBindings(viewModel);
        return viewModel;
    };
})($, _);
