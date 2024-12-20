hqDefine("data_interfaces/js/case_rule_main", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'data_interfaces/js/case_property_input',
    'data_interfaces/js/case_rule_criteria',
    'data_interfaces/js/case_rule_actions',
    'data_interfaces/js/make_read_only',
    'commcarehq',
], function (
    $,
    initialPageData,
    casePropertyInput,
    CaseRuleCriteria,
    CaseRuleActions
) {
    $(function () {
        casePropertyInput.register();

        var criteriaModel = CaseRuleCriteria(
            initialPageData.get('criteria_initial'),
            initialPageData.get('criteria_constants')
        );
        $('#rule-criteria-panel').koApplyBindings(criteriaModel);

        $('#rule-actions').koApplyBindings(CaseRuleActions(
            initialPageData.get('actions_initial'),
            criteriaModel.caseType
        ));
    });
});
