hqDefine('cloudcare/js/gtx', [
    'underscore',
    'analytix/js/gtx',
], function (
    _,
    gtx,
) {
    let lastCaseListSelections = "";
    let lastCaseListTimeMs = Date.now();
    let lastSelections = "";
    let lastSelectionsChangeTimeMs = Date.now();

    const extractSelections = function (menuResponse) {
        return menuResponse.selections ? menuResponse.selections.join(">") : "";
    };

    const logNavigateMenu = function (selections) {
        if (selections !== lastSelections) {
            const navigatedAwayFromCaseList =
                lastCaseListSelections !== "" && !selections.startsWith(lastCaseListSelections);
            const gtxEventData = {
                selections: selections,
                previousSelections: lastSelections,
                navigatedAwayFromCaseList: navigatedAwayFromCaseList,
                caseListSelection: lastCaseListSelections,
                timeSinceLastSelectionChangeMs: Date.now() - lastSelectionsChangeTimeMs,
                timeSinceLastCaseListOpenMs: Date.now() - lastCaseListTimeMs,
            };
            lastSelections = selections;
            lastSelectionsChangeTimeMs = Date.now();
            if (navigatedAwayFromCaseList) {
                lastCaseListSelections = "";
            }
            gtx.sendEvent("web_apps_selection_change", gtxEventData);
        }
    };

    const logCaseList = function (selections, gtxEventData) {
        _.extend(gtxEventData, {
            selections: selections,
        });
        if (selections !== lastCaseListSelections) {
            lastCaseListSelections = selections;
            lastCaseListTimeMs = Date.now();
        }
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
