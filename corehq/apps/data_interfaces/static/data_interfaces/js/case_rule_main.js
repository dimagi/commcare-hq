hqDefine("data_interfaces/js/case_rule_main", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'data_interfaces/js/case_rule_criteria',
    'data_interfaces/js/case_rule_actions',
    'data_interfaces/js/make_read_only',
], function (
    $,
    initialPageData,
    CaseRuleCriteria,
    CaseRuleActions
) {
    $(function () {
        var criteriaModel = CaseRuleCriteria(
            initialPageData.get('criteria_initial'),
            initialPageData.get('criteria_constants'),
            initialPageData.get('all_case_properties')
        );
        // setup tab
        criteriaModel.setScheduleTabVisibility();
        $('#rule-criteria-panel').koApplyBindings(criteriaModel);
        criteriaModel.loadInitial();

        var actionsModel = CaseRuleActions(
            initialPageData.get('actions_initial'),
            criteriaModel.casePropertyNames
        );
        $('#rule-actions').koApplyBindings(actionsModel);
        actionsModel.loadInitial();
    });
});
