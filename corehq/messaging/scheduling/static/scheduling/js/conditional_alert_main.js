import "commcarehq";

import $ from "jquery";
import ko from "knockout";
import _ from "underscore";

import initialPageData from "hqwebapp/js/initial_page_data";

import CaseRuleCriteria from "data_interfaces/js/case_rule_criteria";
import casePropertyInput from "data_interfaces/js/case_property_input";
import "hqwebapp/js/bootstrap3/widgets";
import "scheduling/js/create_schedule";
import "data_interfaces/js/make_read_only";

function BasicInformationTab(name) {
    const self = {};
    self.name = ko.observable(name);
    self.basicTabValid = ko.computed(function () {
        return !_.isEmpty(self.name().trim());
    });
    self.setRuleTabVisibility = function () {
        if (self.basicTabValid()) {
            $("#rule-nav").removeClass("hidden");
        }
    };
    self.navigateToNav = function (navId) {
        $(navId).find('a').trigger('click');
    };
    self.handleBasicNavContinue = function () {
        $("#rule-nav").removeClass("hidden");
        $('#rule-nav').find('a').trigger('click');
    };
    self.setRuleTabVisibility();
    return self;
}

$(function () {
    casePropertyInput.register();

    $("#conditional-alert-basic-info-panel").koApplyBindings(BasicInformationTab(
        initialPageData.get('rule_name'),
    ));

    $('#rule-criteria-panel').koApplyBindings(CaseRuleCriteria(
        initialPageData.get('criteria_initial'),
        initialPageData.get('criteria_constants'),
    ));
});
