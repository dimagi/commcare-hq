"use strict";

var assertProperties = hqImport("hqwebapp/js/assert_properties");

hqDefine('icds_reports/js/spec/utils', function () {
    var module = {};
    module.d = {
        "data": [
            "Ambah",
            0,
        ],
        "index": 0,
        "color": "rgb(0, 111, 223)",
        "value": "Ambah",
        "series": [
            {
                "key": "",
                "value": 0,
                "color": "rgb(0, 111, 223)",
            },
        ],
    };
    module.controllerMapOrSectorViewData = {
        "mapData": {
            "tooltips_data": {
                "Morena -R": {
                    "in_month": 0,
                    "all": 0,
                },
                "Porsa": {
                    "in_month": 0,
                    "all": 0,
                },
                "Morena-U": {
                    "in_month": 0,
                    "all": 0,
                },
                "Ambah": {
                    "in_month": 0,
                    "all": 25,
                },
            },
        },
    };
    module.provideGenders = function ($provide) {
        $provide.constant("genders", [
            {id: '', name: 'All'},
            {id: 'M', name: 'Male'},
            {id: 'F', name: 'Female'},
        ]);
    };
    module.provideAges = function ($provide) {
        $provide.constant('ages', [
            {id: '', name: 'All'},
            {id: '6', name: '0-6 months'},
            {id: '12', name: '6-12 months'},
            {id: '24', name: '12-24 months'},
            {id: '36', name: '24-36 months'},
            {id: '48', name: '36-48 months'},
            {id: '60', name: '48-60 months'},
            {id: '72', name: '60-72 months'},
        ]);
    };
    module.provideQuarters = function ($provide) {
        $provide.constant('quartersOfYear', [
            {id: '1', name: 'Jan-Mar'},
            {id: '2', name: 'Apr-Jun'},
            {id: '3', name: 'Jul-Sep'},
            {id: '4', name: 'Oct-Dec'},
        ]);
    };
    module.provideDataPeriods = function ($provide) {
        $provide.constant('dataPeriods', [
            {id: 'month', name: 'Monthly'},
            {id: 'quarter', name: 'Quarterly'},
        ]);
    };
    module.provideDefaultConstants = function ($provide, options) {
        assertProperties.assert(options, [], ['includeGenders', 'includeAges', 'includeQuarters', 'includeDataPeriods', 'overrides']);
        // overrides should be an object with values of any overrides keyed by the same
        // as the below strings
        function getOverrideOrDefault(key, defaultValue) {
            if (options['overrides'] && options['overrides'].hasOwnProperty(key)) {
                return options['overrides'][key];
            }
            return defaultValue;
        }
        function provideOverrideOrDefault(key, defaultValue) {
            $provide.constant(key, getOverrideOrDefault(key, defaultValue));
        }

        if (options['includeGenders']) {
            module.provideGenders($provide);
        }
        if (options['includeAges']) {
            module.provideAges($provide);
        }
        if (options['includeQuarters']) {
            module.provideQuarters($provide);
        }
        if (options['includeDataPeriods']) {
            module.provideDataPeriods($provide);
        }
        provideOverrideOrDefault("userLocationId", null);
        provideOverrideOrDefault("isAlertActive", false);
        provideOverrideOrDefault("haveAccessToAllLocations", false);
        provideOverrideOrDefault("haveAccessToFeatures", false);
        provideOverrideOrDefault("isMobile", false);
    };
    return module;
});
