/* globals hqDefine, ko, $, _ */

hqDefine('dhis2/js/dhis2_map_settings', function () {
    'use strict';

    var module = {};

    var DataValueMap = function (properties) {
        var self = this;

        self.ucrColumn = ko.observable(properties["column"]);
        self.dataElementId = ko.observable(properties["data_element_id"]);
        self.categoryOptionComboId = ko.observable(properties["category_option_combo_id"]);
        self.dhis2Comment = ko.observable(properties["comment"]);

        self.errors = [];

        self.serialize = function () {
            return {
                "column": self.ucrColumn(),
                "data_element_id": self.dataElementId(),
                "category_option_combo_id": self.categoryOptionComboId(),
                "comment": self.dhis2Comment(),
            };
        };
    };

    var DataSetMap = function (properties) {
        var self = this;

        self.description = ko.observable(properties["description"]);
        self.ucrId = ko.observable(properties["ucr_id"]);
        self.frequency = ko.observable(properties["frequency"]);
        self.dayOfMonth = ko.observable(properties["day_to_send"]);
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
                    self.dataValueMaps.push(new DataValueMap(properties["datavalue_maps"][i]));
                }
            } else {
                self.addDataValueMap();
            }
        };

        self.addDataValueMap = function () {
            self.dataValueMaps.push(new DataValueMap({}));
        };

        self.removeDataValueMap = function (dataValueMap) {
            self.dataValueMaps.remove(dataValueMap);
        };

        self.serialize = function () {
            var dataValueMaps = [];
            for (var i = 0; i < self.dataValueMaps().length; i++) {
                var dataValueMap = self.dataValueMaps()[i];
                dataValueMaps.push(dataValueMap.serialize());
            }
            return {
                "description": self.description(),
                "ucr_id": self.ucrId(),
                "frequency": self.frequency(),
                "day_to_send": Number(self.dayOfMonth()),
                "data_set_id": self.dataSetId(),
                "org_unit_id": self.orgUnitId(),
                "org_unit_column": self.orgUnitIdColumn(),
                "period": self.period(),
                "period_column": self.periodColumn(),
                "attribute_option_combo_id": self.attributeOptionComboId(),
                "complete_date": self.completeDate(),
                "datavalue_maps": dataValueMaps,
            };
        };
    };

    module.Dhis2MapSettings = function (dataSetMaps, sendDataUrl) {
        var self = this;
        var alert_user = hqImport("hqwebapp/js/alert_user").alert_user;

        self.frequencyOptions = [
            {"value": "monthly", "text": "Monthly"},
            {"value": "quarterly", "text": "Quarterly"},
        ];
        self.dataSetMaps = ko.observableArray();

        self.init = function () {
            if (dataSetMaps.length > 0) {
                for (var i = 0; i < dataSetMaps.length; i++) {
                    var dataSetMap = new DataSetMap(dataSetMaps[i]);
                    dataSetMap.init();
                    self.dataSetMaps.push(dataSetMap);
                }
            } else {
                self.addDataSetMap();
            }
        };

        self.addDataSetMap = function () {
            self.dataSetMaps.push(new DataSetMap({}));
        };

        self.removeDataSetMap = function (dataSetMap) {
            self.dataSetMaps.remove(dataSetMap);
        };

        self.submit = function (form) {
            var dataSetMaps = [];
            for (var i = 0; i < self.dataSetMaps().length; i++) {
                var dataSetMap = self.dataSetMaps()[i];
                dataSetMaps.push(dataSetMap.serialize());
            }
            $.post(
                form.action,
                {'dataset_maps': JSON.stringify(dataSetMaps)},
                function (data) { alert_user(data['success'], 'success', true); }
            ).fail(function () { alert_user(gettext('Unable to save DataSet maps'), 'danger'); });
        };

        self.sendData = function () {
            $.post(
                sendDataUrl,
                {},
                function (data) { alert_user(data['success'], 'success', true); }
            );
        };
    };

    return module;
});
