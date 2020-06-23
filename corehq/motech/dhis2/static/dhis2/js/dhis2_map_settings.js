hqDefine('dhis2/js/dhis2_map_settings', [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
    'hqwebapp/js/base_ace',
], function (
    $,
    ko,
    initialPageData,
    alertUser,
    baseAce
) {
    var dataValueMap = function (properties) {
        var self = {};

        self.ucrColumn = ko.observable(properties["column"]);
        self.dataElementId = ko.observable(properties["data_element_id"]);
        self.categoryOptionComboId = ko.observable(properties["category_option_combo_id"]);
        self.dhis2Comment = ko.observable(properties["comment"]);

        self.errors = [];

        self.toJSON = function () {
            return {
                "column": self.ucrColumn(),
                "data_element_id": self.dataElementId(),
                "category_option_combo_id": self.categoryOptionComboId(),
                "comment": self.dhis2Comment(),
            };
        };

        return self;
    };

    var dataSetMap = function (properties) {
        var self = {};

        self.description = ko.observable(properties["description"]);
        self.connectionSettingsId = ko.observable(properties["connection_settings_id"]);
        self.ucrId = ko.observable(properties["ucr_id"]);
        self.frequency = ko.observable(properties["frequency"]);
        self.dayToSend = ko.observable(properties["day_to_send"]);
        self.dataSetId = ko.observable(properties["data_set_id"]);

        self.orgUnitId = ko.observable(properties["org_unit_id"]);
        self.orgUnitIdColumn = ko.observable(properties["org_unit_column"]);
        self.orgUnitIdRadio = ko.observable(properties["org_unit_id"] ? "value" : "column");

        self.period = ko.observable(properties["period"]);
        self.periodColumn = ko.observable(properties["period_column"]);
        self.periodRadio = ko.observable(
            properties["period"] ? "value" : properties["period_column"] ? "column" : "filter"
        );

        self.attributeOptionComboId = ko.observable(properties["attribute_option_combo_id"]);
        self.completeDate = ko.observable(properties["complete_date"]);
        self.dataValueMaps = ko.observableArray();

        self.errors = [];

        self.init = function () {
            if (properties.hasOwnProperty("datavalue_maps") && properties["datavalue_maps"].length > 0) {
                for (var i = 0; i < properties["datavalue_maps"].length; i++) {
                    self.dataValueMaps.push(dataValueMap(properties["datavalue_maps"][i]));
                }
            } else {
                self.addDataValueMap();
            }
        };

        self.addDataValueMap = function () {
            self.dataValueMaps.push(dataValueMap({}));
        };

        self.removeDataValueMap = function (dataValueMap) {
            self.dataValueMaps.remove(dataValueMap);
        };

        self.toJSON = function () {
            return {
                "description": self.description(),
                "connection_settings_id": Number(self.connectionSettingsId()),
                "ucr_id": self.ucrId(),
                "frequency": self.frequency(),
                "day_to_send": Number(self.dayToSend()),
                "data_set_id": self.dataSetId(),
                "org_unit_id": self.orgUnitId(),
                "org_unit_column": self.orgUnitIdColumn(),
                "period": self.period(),
                "period_column": self.periodColumn(),
                "attribute_option_combo_id": self.attributeOptionComboId(),
                "complete_date": self.completeDate(),
                "datavalue_maps": self.dataValueMaps(),
            };
        };

        return self;
    };

    var jsonDataSetMap = function (data) {
        var self = {};

        self.dataSetMap = ko.observable(JSON.stringify(data, null, 2));

        self.init = function () {
            // So that jsonDataSetMap object ducktypes dhis2MapSettings.dataSetMap object
        };

        self.toJSON = function () {
            return JSON.parse(self.dataSetMap());
        };

        return self;
    };


    var dhis2MapSettings = function (dataSetMaps, sendDataUrl, isJsonUi) {
        var self = {};

        self.frequencyOptions = [
            {"value": "weekly", "text": "Weekly"},
            {"value": "monthly", "text": "Monthly"},
            {"value": "quarterly", "text": "Quarterly"},
        ];
        self.dataSetMaps = ko.observableArray();

        self.init = function () {
            if (dataSetMaps.length > 0) {
                for (var i = 0; i < dataSetMaps.length; i++) {
                    var data = dataSetMaps[i],
                        map = isJsonUi ? jsonDataSetMap(data) : dataSetMap(data);
                    map.init();
                    self.dataSetMaps.push(map);
                }
            } else {
                self.addDataSetMap();
            }
        };

        self.addDataSetMap = function () {
            var map = isJsonUi ? jsonDataSetMap('{}') : dataSetMap({});
            self.dataSetMaps.push(map);
        };

        self.initDataSetMapTemplate = function (elements) {
            _.each(elements, function (element) {
                _.each($(element).find('.jsonwidget'), baseAce.initObservableJsonWidget);
            });
        };

        self.removeDataSetMap = function (dataSetMap) {
            self.dataSetMaps.remove(dataSetMap);
        };

        self.submit = function (form) {
            $.post(
                form.action,
                {'dataset_maps': JSON.stringify(self.dataSetMaps())},
                function (data) { alertUser.alert_user(data['success'], 'success', true); }
            ).fail(function () { alertUser.alert_user(gettext('Unable to save DataSet maps'), 'danger'); });
        };

        self.sendData = function () {
            $.post(
                sendDataUrl,
                {},
                function (data) { alertUser.alert_user(data['success'], 'success', true); }
            );
        };

        return self;
    };

    $(function () {
        var viewModel = dhis2MapSettings(
            initialPageData.get('dataset_maps'),
            initialPageData.get('send_data_url'),
            initialPageData.get('is_json_ui')
        );
        viewModel.init();
        $('#dataset-maps').koApplyBindings(viewModel);
    });
});
