hqDefine('cloudcare/js/gtx', [
    'underscore',
    'analytix/js/gtx',
], function (
    _,
    gtx,
) {
    let lastNavigationTimeMs = Date.now();
    let lastCaseListSelections = "";
    let lastCaseListTimeMs = Date.now();
    let lastSelections = "";
    let lastSelectionsChangeTimeMs = Date.now();

    const extractSelections = function (menuResponse) {
        return menuResponse.selections ? menuResponse.selections.join(">") : "";
    };

    const logNavigateMenu = function (selections) {
        const selectionsChanged = selections !== lastSelections;
        const navigatedAwayFromCaselist =
            lastCaseListSelections !== "" && !selections.startsWith(lastCaseListSelections);
        const gtxEventData = {
            timeSinceLastNavigationMs: Date.now() - lastNavigationTimeMs,
            selections: selections,
            previousSelections: lastSelections,
            selectionsChanged: selectionsChanged,
            navigatedAwayFromCaseList: navigatedAwayFromCaselist,
            caseListSelection: lastCaseListSelections,
            timeSinceLastSelectionChangeMs: Date.now() - lastSelectionsChangeTimeMs,
            timeSinceLastCaseListOpenMs: Date.now() - lastCaseListTimeMs,
        };
        if (selectionsChanged) {
            lastSelections = selections;
            lastSelectionsChangeTimeMs = Date.now();
        }
        if (navigatedAwayFromCaselist) {
            lastCaseListSelections = "";
        }
        lastNavigationTimeMs = Date.now();
        gtx.sendEvent("web_apps_navigate", gtxEventData);
    };

    const logCaseList = function (selections, gtxEventData) {
        if (selections !== lastCaseListSelections) {
            lastCaseListSelections = selections;
            lastCaseListTimeMs = Date.now();
        }
        _.extend(gtxEventData, {
            selections: selections,
        });
        gtx.sendEvent("web_apps_viewed_case_list", gtxEventData);
    };

    const logFormSubmit = function (gtxEventData) {
        _.extend(gtxEventData, {
            navigatedAwayFromCaseList: true,
            timeSinceLastCaseListOpenMs: Date.now() - lastCaseListTimeMs,
            caseListSelection: lastCaseListSelections,
        });
        lastCaseListSelections = "";
        gtx.sendEvent("web_apps_submit_form", gtxEventData);
    };

    return {
        extractSelections: extractSelections,
        logCaseList: logCaseList,
        logFormSubmit: logFormSubmit,
        logNavigateMenu: logNavigateMenu,
    };
});
