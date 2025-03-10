const { expr } = require("jquery");

hqDefine('cloudcare/js/gtx', [
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

    const logCaseList = function (menuResponse) {
        const selections = extractSelections(menuResponse);
        const gtxEventData = {
            selections: selections,
            moduleName: menuResponse.title,
        };
        if (selections !== lastCaseListSelections) {
            lastCaseListSelections = selections;
            lastCaseListTimeMs = Date.now();
            lastCaseListModuleName = menuResponse.title;
        }
        gtx.sendEvent("web_apps_viewed_case_list", gtxEventData);
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
    };
});
