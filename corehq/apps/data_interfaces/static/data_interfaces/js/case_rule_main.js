import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import casePropertyInput from "data_interfaces/js/case_property_input";
import CaseRuleCriteria from "data_interfaces/js/case_rule_criteria";
import CaseRuleActions from "data_interfaces/js/case_rule_actions";
import "data_interfaces/js/make_read_only";

$(function () {
    casePropertyInput.register();

    var criteriaModel = CaseRuleCriteria(
        initialPageData.get('criteria_initial'),
        initialPageData.get('criteria_constants'),
    );
    $('#rule-criteria-panel').koApplyBindings(criteriaModel);

    $('#rule-actions').koApplyBindings(CaseRuleActions(
        initialPageData.get('actions_initial'),
        criteriaModel.caseType,
    ));
});
