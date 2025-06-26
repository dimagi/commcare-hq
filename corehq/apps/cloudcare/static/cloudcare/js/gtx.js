define('cloudcare/js/gtx', [
    'underscore',
    'analytix/js/gtx',
], function (
    _,
    gtx,
) {
    let lastCaseListSelections = "";
    let lastCaseListModuleName = "";
    let lastCaseListTimeMs = Date.now();
    let lastSelections = "";
    let lastSelectionsChangeTimeMs = Date.now();

    const extractSelections = function (menuResponse) {
        return menuResponse.selections ? ">" + menuResponse.selections.join(">") : "";
    };

    const logStartForm = function (name) {
        const gtxEventData = {
            title: name,
        };
        gtx.sendEvent("web_apps_start_form", gtxEventData);
    };

    const logNavigateMenu = function (menuResponse) {
        const selections = extractSelections(menuResponse);
        if (selections !== lastSelections) {
            const navigatedAwayFromCaseList =
                lastCaseListSelections !== "" && !selections.startsWith(lastCaseListSelections);
            const gtxEventData = {
                selections: selections,
                previousSelections: lastSelections,
                navigatedAwayFromCaseList: navigatedAwayFromCaseList,
                caseListSelection: lastCaseListSelections,
                caseListModuleName: lastCaseListModuleName,
                timeSinceLastSelectionChangeMs: Date.now() - lastSelectionsChangeTimeMs,
                timeSinceLastCaseListOpenMs: Date.now() - lastCaseListTimeMs,
            };
            lastSelections = selections;
            lastSelectionsChangeTimeMs = Date.now();
            if (navigatedAwayFromCaseList) {
                lastCaseListSelections = "";
                lastCaseListModuleName = "";
            }
            gtx.sendEvent("web_apps_selection_change", gtxEventData);
        }
    };

    const logCaseList = function (menuResponse, searchFieldList) {
        const selections = extractSelections(menuResponse);
        let gtxEventData = {
            selections: selections,
            moduleName: menuResponse.title,
        };
        if (searchFieldList.length > 0) {
            searchFieldData = formatSearchFieldData(searchFieldList);
            searchFieldData.searchFieldsLength = searchFieldList.join(",").length;
            gtxEventData = Object.assign(gtxEventData, searchFieldData);
        }
        if (selections !== lastCaseListSelections) {
            lastCaseListSelections = selections;
            lastCaseListTimeMs = Date.now();
            lastCaseListModuleName = menuResponse.title;
        }
        gtx.sendEvent("web_apps_viewed_case_list", gtxEventData);
    };

    // Google Analytics can only display up 100 characters. This splits the search field across 3 strings,
    // the first 2 capped at 100 characters and the third holding the rest, so that we can show more data in GA.
    var formatSearchFieldData = function (searchFields) {
        const concatFields = {};
        const maxFields = 3;
        let currentField = 1;
        let currentString = '';
        let maxStringLength = 100;
        for (var i = 0; i < searchFields.length; i++) {
            const field = searchFields[i];
            if (currentField < maxFields) {
                if (currentString.length === 0) {
                    currentString = field;
                } else if (currentString.length + 1 + field.length <= maxStringLength) {
                    currentString += "," + field;
                } else {
                    concatFields['searchFields' + currentField] = currentString;
                    currentField += 1;
                    currentString = field;
                }
            } else {
                const remainingFields = searchFields.slice(i - 1).join(",");
                concatFields['searchFields3'] = remainingFields;
                return concatFields;
            }
        }
        if (currentString.length > 0) {
            concatFields['searchFields' + currentField] = currentString;
        }
        return concatFields;
    };

    const logFormSubmit = function (gtxEventData) {
        _.extend(gtxEventData, {
            navigatedAwayFromCaseList: lastCaseListSelections !== "",
            timeSinceLastCaseListOpenMs: Date.now() - lastCaseListTimeMs,
            caseListSelection: lastCaseListSelections,
            caseListModuleName: lastCaseListModuleName,
        });
        lastCaseListSelections = "";
        lastCaseListModuleName = "";
        gtx.sendEvent("web_apps_submit_form", gtxEventData);
    };

    return {
        extractSelections: extractSelections,
        logCaseList: logCaseList,
        logFormSubmit: logFormSubmit,
        logNavigateMenu: logNavigateMenu,
        logStartForm: logStartForm,
    };
});
