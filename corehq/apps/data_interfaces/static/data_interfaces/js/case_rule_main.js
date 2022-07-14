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
        $('#rule-criteria-panel').koApplyBindings(CaseRuleCriteria(
            initialPageData.get('criteria_initial'),
            initialPageData.get('criteria_constants'),
            initialPageData.get('all_case_properties')
        ));

        $('#rule-actions').koApplyBindings(CaseRuleActions(
            initialPageData.get('actions_initial'),
            criteriaModel.casePropertyNames
        ));
    });
});
