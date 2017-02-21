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

function findLocationTypeCode(level) {
    for (var key in LOCATIONS_MAP) {
        if (LOCATIONS_MAP.hasOwnProperty(key)) {
            var value = LOCATIONS_MAP[key];
            if (value === level) {
                return key;
            }
        }
    }
}

function resetFilters() {
    var today = new Date();
    var twoDigitMonth = ("0" + (today.getMonth() + 1)).slice(-2);

    $('#report_filter_month').select2('val', twoDigitMonth);
    $('#report_filter_year').select2('val', today.getFullYear());
    $("#report_filter_caste").select2('val', 'All');
    $("#report_filter_child_age_tranche").select2('val', 'All');
    $("#report_filter_minority").select2('val', 'All');
    $("#report_filter_disabled").select2('val', 'All');
    $("#report_filter_resident").select2('val', 'All');
    $("#report_filter_ccs_status").select2('val', 'All');
    $("#report_filter_thr_beneficiary_type").select2('val', 'All');

    var locationKOContext = ko.dataFor($('#group_location_async')[0]);
    locationKOContext.reset();
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

    var locationTypeCode = findLocationTypeCode(locationLevel);

    var filters = {
        Month: dateStr,
        Caste: caste,
        child_age_tranche: childAge,
        Minority: minority,
        Disabled: disabled,
        Resident: resident,
        ccs_status: maternalStatus,
        thr_beneficiary_type: beneficiaryType,
        state: selectedUUIDs[0] || 'All',
        district: selectedUUIDs[1] || 'All',
        block: selectedUUIDs[2] || 'All',
        view_by: locationLevel,
        user_state: '',
        user_district: '',
        user_block: '',
        user_national: '',
    };

    filters['user_' + locationTypeCode] = selectedUUIDs[0] || selectedUUIDs[1] || selectedUUIDs[2] || 'All';
    return filters;
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
            setUpWorkbook(viz);
            setUpInitialTableauParams();
            setUpNav(viz);
        },
    };
    viz = new tableau.Viz(placeholderDiv, url, options);

    $("#resetFilters").click(function () {
        var currentSheet = history.state.sheetName;
        resetFilters();
        switchVisualization(currentSheet, workbook, getFiltersValues());
    });

    $("#applyFilters").click(function() {
        var currentSheet = history.state.sheetName;
        switchVisualization(currentSheet, workbook, getFiltersValues());
    });
}

function setUpWorkbook(viz) {
    workbook = viz.getWorkbook();
}

function setUpInitialTableauParams() {
    var locationKey = 'user_' + tableauOptions.userLocationLevel;
    var params = {
        'view_by': LOCATIONS_MAP[tableauOptions.userLocationLevel],
        'state': tableauOptions.stateCode,
        'district': tableauOptions.districtCode,
        'block': tableauOptions.blockCode,
    };
    params[locationKey] = tableauOptions.userLocation;
    var today = new Date();
    var lastMonth = new Date(today.getFullYear(), today.getMonth() - 1 , 1);
    params['Month'] = lastMonth.getFullYear() + "-" + (lastMonth.getMonth() + 1) + "-01";
    applyParams(workbook, params);

    var historyObject = {
        'sheetName': tableauOptions.currentSheet,
        'params': params,
    };
    history.pushState(historyObject, '', tableauOptions.currentSheet);
}

function setUpNav(viz) {
    var sheets = workbook.getPublishedSheetsInfo();

    // Filter out the sheets for a single AWC. These are accessed via drilldown
    sheets = _.filter(sheets, function(sheet) {
        return (sheet.getName() !== "Demographics" && sheet.getName() !== 'AWC-Info');
    });
    _.each(sheets, function(sheet) {
        addNavigationLink(sheet.getName(), sheet.getIsActive());
    });

    $(".nav-link").click(function (e){
        var link = $(this);
        var sheetName = link[0].textContent;
        var params = history.state.params;
        navigateToSheet(sheetName, workbook, params);
        e.preventDefault();
    });

    viz.addEventListener(tableau.TableauEventName.MARKS_SELECTION, onMarksSelection);
}

function addNavigationLink(sheetName) {
    var html = "<li><a href='#' class='nav-link'>" + sheetName + "</a></li>";
    $(".dropdown-menu").append(html);
}

function onMarksSelection(marksEvent) {
    return marksEvent.getMarksAsync().then(updateViz);
}

/*
From selected marks, extracts new sheet to render, new paramters/filters to apply, and updates the viz with them

ICDS workbooks will have new sheet/paramter info in following attributes of the mark

- 'js_sheet: <sheet name to navigate to>': New sheet to navigate to
    e.g. js_sheet: Nutrition
- 'js_param_<param_name>: <param_value>': New paramters to apply
    e.g. js_param_state: Andhra Pradesh
*/
function updateViz(marks) {
    clearDebugInfo();
    // marks is an array of what the user has clicked
    var debugHtml = ["<ul>"],
        // default the sheet to navigate to to the current one
        currentSheet = history.state.sheetName,
        newSheet = currentSheet;
        var newParams = {};

    function buildParams(currentParams) {

        _.each(marks, function(mark) {
            var pairs = mark.getPairs();

            _.each(pairs, function(pair){
                debugHtml.push("<li><b>" + pair.fieldName + "</b>: "+ pair.formattedValue + "</li>");
                newSheet = extractSheetName(pair, newSheet);
                var newParam = extractParam(pair, currentParams);
                $.extend(newParams, newParam);
            });

            debugHtml.push("</ul>");
        });

        debugHtml = debugHtml.join("");

        $("#debugbar").append(debugHtml);

        // Add inspect button listener
        if( tableauOptions.isDebug ) {
            $("#inspectButton").unbind('click').click(function() {
                switchVisualization(newSheet, workbook, newParams);
            }).prop('disabled', false);
        } else {
            switchVisualization(newSheet, workbook, newParams);
        }

    }

    workbook.getParametersAsync()
        .then(buildParams)
        .otherwise(function(err) {
            // TODO: Better error rendering
            alert(err);
        });
}

/*
Extracts the hardcoded param-list for the sheetName and renders the sheet with given params and extracted params

ICDS workbook will have following paramter convention
- 'js_sheet_<sheet_name>: json-string specifying new params as key-value pairs':
    e.g. js_sheet_Nutrition: '{"is_drilldown": "True"}'
*/
function navigateToSheet(sheetName, workbook, params){

    workbook.getParametersAsync()
        .then(changeViz)
        .otherwise(function(err) {
            // TODO: Better error rendering
            alert(err);
        });

    function changeViz(currentParams) {
        var extraParams = extractHardcodedSheetParams(currentParams, sheetName);
        $.extend(params, extraParams);
        switchVisualization(sheetName, workbook, params);
    }

}

/*
Given attribute key-value pair, extracts new sheetName specified in 'js_sheet: <new_sheet>', if attribute name is
not js_sheet returns current sheetName
*/
function extractSheetName(pair, sheetName) {
    if((pair.fieldName === 'js_sheet' || pair.fieldName === 'ATTR(js_sheet)') && pair.formattedValue !== 'CURRENT') {
        return pair.formattedValue;
    }
    return sheetName;
}

function switchVisualization(sheetName, workbook, params) {
    // TODO: Handle the case where we are in the same sheet, might just need to apply filters then?
    var worksheets;
    workbook.activateSheetAsync(sheetName)
            .then(function(dashboard) {
                worksheets = dashboard.getWorksheets();

                // I need the last worksheet to return a promise like object when all the iteration is complete
                var lastWorksheet = applyParams(workbook, params, lastWorksheet);

                // TODO: historyObject should be an actual object
                var historyObject = {
                    'sheetName': sheetName,
                    'params': params,
                };
                history.pushState(historyObject, sheetName, sheetName);
                return lastWorksheet;
            }).otherwise(function(err){
                // TODO: same thing with this alert as above
                alert(err);
            });

}

function applyParams(workbook, params, lastWorksheet) {
    _.each(params, function(value, key) {
        // TODO: This is the last param to be set, not the last to finish executing. Need to only run when last param is set (something like _.join())
        lastWorksheet = workbook.changeParameterValueAsync(key, value);
    });
    return lastWorksheet;
}

function clearDebugInfo() {
    $("#debugbar").empty();
    // TODO: Disabling the button doesn't work
    $("#inspectButton").prop('disabled', true);
}

window.onpopstate = function (event) {
    if(!event.state.sheetName) {
        alert('History object needs a location to navigate to');
    }
    if(event.state.sheetName === 'base') {
        viz.revertAllAsync();
        clearDebugInfo();
    } else {
        workbook.activateSheetAsync(event.state.sheetName).then(function() {
            applyParams(workbook, event.state.params);
        }).otherwise(function(err) {
            alert(err);
        });
    }
};

/*
Given an attribute pair and existingParams, extracts and returns new paramter specified by
'js_param_<paramname>: <paramvalue>'
*/
function extractParam(pair, currentParams){
    var newParam = {};
    var PARAM_SUBSTRING = 'ATTR(js_param_',
        PARAM_UNCHANGED = 'CURRENT';
    if(pair.fieldName.includes(PARAM_SUBSTRING)) {
        var param_key = pair.fieldName.slice(PARAM_SUBSTRING.length, -1),
            param_value = pair.formattedValue;

        if(param_value === PARAM_UNCHANGED) {
            newParam[param_key] = getParamValue(currentParams, param_key);
        } else {
            newParam[param_key] = param_value;
        }
    }
    return newParam;
}


function getParamValue(params, param_key){
    var matchingParams = _.filter(params, function(param) {
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

/*
Extracts hardcoded JSON paramters for sheetName specified in a param called 'js_sheet_<sheetName>'
*/
function extractHardcodedSheetParams(params, sheetName){
    var key = 'js_sheet_' + sheetName;
    var sheetParam = getParamValue(params, key);

    if (sheetParam && sheetParam.formattedValue) {
        try {
            return JSON.parse(sheetParam.formattedValue);
        }
        catch(e) {
            return {};
        }
    }
    else {
        return {};
    }
}
