/*global _ tableau */

var viz = {},
    workbook = {},
    LOCATIONS_MAP = {
        'national': 1,
        'state': 2,
        'district': 3,
        'block': 4,
        'supervisor': 5,
        'awc': 6,
    };

var tableauOptions = {};
var initialParams = {};
var initialLocationData = {};
var awcOnlySheets = [];

function getLocationData() {
    var locationKOContext = ko.dataFor($('#group_location_async')[0]);
    return {
        locations: locationKOContext.root().toPlainJS().children,
        selected: locationKOContext.selected_locid(),
    };
}

function updateLocationFilter(locationData) {
    var locationKOContext = ko.dataFor($('#group_location_async')[0]);
    locationKOContext.selected_path([]);
    locationKOContext.load(locationData.locations, locationData.selected);
}

function getFiltersValues() {
    var month = $('#report_filter_month').val();
    var year = $('#report_filter_year').val();
    var dateStr = year + '-' + month + '-01';

    var caste = $('#report_filter_caste').val();
    var childAge = $('#report_filter_child_age_tranche').val();
    var minority = $('#report_filter_minority').val();
    var disabled = $('#report_filter_disabled').val();
    var resident = $('#report_filter_resident').val();
    var maternalStatus = $('#report_filter_ccs_status').val();
    var beneficiaryType = $('#report_filter_thr_beneficiary_type').val();
    var locationKOContext = ko.dataFor($('#group_location_async')[0]);

    var selectedUUIDs = [];
    var locationLevel = 1;

    locationKOContext.selected_path().forEach(function(loc) {
        var uuid = loc.uuid();
        if (uuid) {
            selectedUUIDs.push(uuid);
            locationLevel++;
        }
    });

    if (locationKOContext.selected_location() && locationKOContext.selected_location().type() === 'awc') {
        selectedUUIDs[locationLevel - 1] = locationKOContext.selected_locid();
        locationLevel++;
    }

    var state = selectedUUIDs[0];
    var district = selectedUUIDs[1];
    var block = selectedUUIDs[2];
    var supervisor = selectedUUIDs[3];
    var awc = selectedUUIDs[4];

    var filters = {
        month: dateStr,
        caste: caste,
        child_age_tranche: childAge,
        minority: minority,
        disabled: disabled,
        resident: resident,
        ccs_status: maternalStatus,
        thr_beneficiary_type: beneficiaryType,
        state: state || 'All',
        district: district || 'All',
        block: block || 'All',
        supervisor: supervisor || 'All',
        awc: awc || 'All',
    };

    return filters;
}

function setFiltersValues(params, locationData) {
    if (locationData) {
        updateLocationFilter(locationData);
    }

    var date = new Date(params.month);
    var twoDigitMonth = ("0" + (date.getUTCMonth() + 1)).slice(-2);
    $('#report_filter_month').select2('val', twoDigitMonth);
    $('#report_filter_year').select2('val', date.getUTCFullYear());

    $("#report_filter_caste").select2('val', params.caste);
    $("#report_filter_minority").select2('val', params.minority);
    $("#report_filter_disabled").select2('val', params.disabled);
    $("#report_filter_resident").select2('val', params.resident);
    $("#report_filter_ccs_status").select2('val', params.ccs_status);
    $("#report_filter_child_age_tranche").select2('val', params.child_age_tranche);
    $("#report_filter_thr_beneficiary_type").select2('val', params.thr_beneficiary_type);
}

function initializeViz(o) {
    tableauOptions = o;
    var placeholderDiv = document.getElementById("tableauPlaceholder");
    var url = tableauOptions.tableauUrl;
    var options = {
        width: placeholderDiv.offsetWidth,
        height: placeholderDiv.offsetHeight,
        hideTabs: true,
        hideToolbar: true,
        onFirstInteractive: function () {
            workbook = viz.getWorkbook();
            workbook.getParametersAsync().then(function(tableauParams) {
                var awcOnlySheetsJSON = getParamValue(tableauParams, 'js_awc_only_sheets');
                if (awcOnlySheetsJSON) {
                    awcOnlySheets = JSON.parse(awcOnlySheetsJSON.value);
                }
                setUpNav(viz);
                setUpInitialTableauParams();
            });
        },
    };
    viz = new tableau.Viz(placeholderDiv, url, options);

    $("#resetFilters").click(function () {
        setFiltersValues(initialParams, initialLocationData);
        pushParams(initialParams, null);
    });

    $("#applyFilters").click(function() {
        pushParams(getFiltersValues(), null);
    });
}

function setUpInitialTableauParams() {
    var params = getFiltersValues();
    var sheetName = tableauOptions.currentSheet;
    initialParams = _.clone(params);
    initialLocationData = getLocationData();

    pushParams(params, sheetName);
}

function setUpNav(viz) {
    var sheets = workbook.getPublishedSheetsInfo();

    // Filter out the sheets for a single AWC. These are accessed via drilldown
    sheets = _.filter(sheets, function(sheet) {
        return !_.contains(awcOnlySheets, sheet.getName());
    });
    _.each(sheets, function(sheet) {
        var html = "<li><a href='#' class='nav-link'>" + sheet.getName() + "</a></li>";
        $(".dropdown-menu").append(html);
    });

    $(".nav-link").click(function (e){
        var link = $(this);
        var sheetName = link[0].textContent;
        //No need to change params when changing sheets
        pushParams({}, sheetName);
        e.preventDefault();
    });

    viz.addEventListener(tableau.TableauEventName.MARKS_SELECTION, onMarksSelection);
}

/*
Navigation back in the UI.
*/
window.onpopstate = function (event) {
    popParams(event.state.params, event.state.sheetName, event.state.locationData)
};

function onMarksSelection(marksEvent) {
    /*
    Given an attribute pair and existingParams, extracts and returns new paramter specified by
    'js_param_<paramname>: <paramvalue>'
    */
    function extractParam(pair, currentTableauParams){
        var newParam = {};
        var PARAM_SUBSTRING = 'ATTR(js_param_',
            PARAM_UNCHANGED = 'CURRENT';
        if(pair.fieldName.includes(PARAM_SUBSTRING)) {
            var param_key = pair.fieldName.slice(PARAM_SUBSTRING.length, -1),
                param_value = pair.formattedValue;

            if(param_value === PARAM_UNCHANGED) {
                newParam[param_key] = getParamValue(currentTableauParams, param_key);
            } else {
                newParam[param_key] = param_value;
            }
        }
        return newParam;
    }

    /*
    From selected marks, extracts new sheet to render, new paramters/filters to apply, and updates the viz with them

    ICDS workbooks will have new sheet/paramter info in following attributes of the mark

    - 'js_sheet: <sheet name to navigate to>': New sheet to navigate to
        e.g. js_sheet: Nutrition
    - 'js_param_<param_name>: <param_value>': New paramters to apply
        e.g. js_param_state: Andhra Pradesh
    */
    function applyMarks(marks) {
        workbook.getParametersAsync().then(function(currentTableauParams) {
            var newParams = {};
            newSheet = null;
            _.each(marks, function(mark) {
                var pairs = mark.getPairs();
                _.each(pairs, function(pair){
                    if((pair.fieldName === 'js_sheet' || pair.fieldName === 'ATTR(js_sheet)') && pair.formattedValue !== 'CURRENT') {
                        newSheet = pair.formattedValue;
                    }
                    var newParam = extractParam(pair, currentTableauParams);
                    $.extend(newParams, newParam);
                });
            });

            pushParams(newParams, newSheet);
        }).otherwise(function(err) {
            // TODO: Better error rendering
            alert(err);
        });
    }

    return marksEvent.getMarksAsync().then(applyMarks);
}

/*
    This will process and update the params and then apply to the viz.  sheetName is optional
*/
function processAndApplyParams(navigationContext) {
    function applyParams(params) {
        _.each(params, function(value, key) {
            workbook.changeParameterValueAsync(key, value);
        });
    }

    //Override the sheetName if someone is filtering to the AWC level (or moving away)
    var currentParams = getCurrentParams();
    if (currentParams.awc === 'All' && navigationContext.params.awc !== 'All' && !_.contains(awcOnlySheets, navigationContext.sheetName)) {
        //User manually filtered to a single AWC
        navigationContext.sheetName = 'AWC-Info';
    } else if (currentParams.awc !== 'All' && navigationContext.params.awc === 'All' && _.contains(awcOnlySheets, navigationContext.sheetName)) {
        //User changed the filter away from an AWC and is currently on an AWC only sheet
        navigationContext.sheetName = 'Dashboard';
    } else if (currentParams.awc !== 'All' && !_.contains(awcOnlySheets, navigationContext.sheetName)) {
        //User was on AWC only page then changed the report to one that does not support a single AWC
        navigationContext.params.awc = 'All';
        navigationContext.locationData.selected = navigationContext.params.supervisor;
        updateLocationFilter(navigationContext.locationData);
    }

    //Calculate View By (based on if a location level is set and its value)
    if (navigationContext.params.state === 'All') {
        navigationContext.params.view_by = 1;
    } else if (navigationContext.params.district === 'All') {
        navigationContext.params.view_by = 2;
    } else if (navigationContext.params.block === 'All') {
        navigationContext.params.view_by = 3;
    } else if (navigationContext.params.supervisor === 'All') {
        navigationContext.params.view_by = 4;
    } else if (navigationContext.params.awc === 'All') {
        navigationContext.params.view_by = 5;
    } else {
        navigationContext.params.view_by = 6;
    }

    //If there is a sheet, do a navigation, otherwise just apply the new parameters
    if (!navigationContext.sheetName) {
        applyParams(navigationContext.params);
    } else {
        workbook.activateSheetAsync(navigationContext.sheetName).then(function(dashboard) {
            applyParams(navigationContext.params);
        });
    }
}

/*
    This function will apply the desired parameters and sheet and add an entry
    to the browser history.  sheetName is optional
*/
function pushParams(params, sheetName) {
    //Extend params with currentParams so we have a full set
    var navigationContext = {
        sheetName: sheetName,
        params: $.extend({}, getCurrentParams(), params),
        locationData: getLocationData(),
    };
    //navigation context will get updated by function
    processAndApplyParams(navigationContext);

    if (!navigationContext.sheetName) {
        navigationContext.sheetName = history.state.sheetName;
    }
    history.pushState(navigationContext, sheetName, sheetName);
}

/*
    This function will reset the UI filters and update the viz.  Its used when popping from the browser history
*/
function popParams(params, targetSheet, locationData) {
    setFiltersValues(params, locationData);
    var navigationContext = {
        sheetName: sheetName,
        params: params,
        locationData: locationData,
    };
    processAndApplyParams(navigationContext);
}

function getCurrentParams() {
    if (history.state && history.state.params) {
        return history.state.params;
    }
    return {}
}

/*
    Will return a parameter value from an array of TableauParameters
*/
function getParamValue(tableauParams, param_key) {
    var matchingParams = _.filter(tableauParams, function(param) {
        return param.getName() === param_key;
    });
    // There should be one matching param
    if (matchingParams.length !== 0){
        return matchingParams[0].getCurrentValue();
    }
    else {
        return null;
    }
}