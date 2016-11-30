/* globals django */
(function ($, _) {
    var CaseProperty = function (caseType, data, casePropertyUrl) {
        var self = this;

        self.caseType = ko.observable(caseType);
        self.name = ko.observable(data.name);
        self.description = ko.observable(data.description);
        self.dataType = ko.observable(data.type);
        self.availableDataTypes = ko.observableArray([
            {value: 'date', display: django.gettext('Date')},
            {value: 'plain', display: django.gettext('Plain')},
            {value: 'number', display: django.gettext('Number')},
            {value: 'select', display: django.gettext('Select')},
            {value: 'integer', display: django.gettext('Integer')},
        ]);

        self.dataType.subscribe(function (newType) {
            if (newType) {
                $.ajax({
                    url: casePropertyUrl,
                    type: 'POST',
                    dataType: 'JSON',
                    data: {
                        'caseType': self.caseType(),
                        'name': self.name,
                        'type': newType,
                    },
                    success: function () { },
                    // todo show errors
                    error: function () { },
                });
            }
        }, self);
    };

    var CaseType = function (name, casePropertyUrl) {
        var self = this;
        self.name = ko.observable(name);
        self.properties = ko.observableArray();

        self.init = function (properties) {
            _.each(properties, function (property) {
                self.properties.push(new CaseProperty(self.name, property, casePropertyUrl));
            });
        };
    };

    var DataDictionaryModel = function (dataUrl, casePropertyUrl) {
        var self = this;
        self.caseTypes = ko.observableArray();
        self.activeCaseType = ko.observable();

        self.init = function () {
            $.getJSON(dataUrl)
            .done(function (data) {
                _.each(data.case_types, function (caseType) {
                    var caseTypeObj = new CaseType(caseType.name, casePropertyUrl);
                    caseTypeObj.init(caseType.properties);
                    self.caseTypes.push(caseTypeObj);
                });
                self.goToCaseType(self.caseTypes()[0]);
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
            self.activeCaseType(caseType.name());
        };
    };

    $.fn.initializeDataDictionary = function (dataUrl, casePropertyUrl) {
        var viewModel = new DataDictionaryModel(dataUrl, casePropertyUrl);
        viewModel.init();
        $(this).koApplyBindings(viewModel);
        return viewModel;
    };
})($, _);
