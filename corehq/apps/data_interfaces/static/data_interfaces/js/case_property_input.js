/*
 * Component to input for a case property.
 *
 * If the domain has the data dictionary privilege, this input will be a select2
 * populated with case properties from the data dictionary. It will not
 * include system properties such as case name or date opened.
 * If the domain does not have the data dictionary privilege, the input will be a text input.
 *
 * Required parameters
 * - caseTypeObservable: observable storing the relevant case type, necessary so
 *   that autocomplete options can be updated when the case type changes
 * - valueObservable: observable to use as the input's value
 *
 * Usage
 * - The page must have an "all_case_properties" item provided to initial page data,
 *   which should be an object where keys are case type names and values are arrays
 *   of case property names.
 * - The calling code must call the `register` function to initialize the component
 *   Note this must be done on DOM ready, so that initial page data is available.
 * - The widget itself is a custom HTML element:
 *     <case-property-input params="
 *       valueObservable: name,
 *       caseTypeObservable: $root.caseType,
 *     "></case-property-input>
 */
hqDefine('data_interfaces/js/case_property_input', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/privileges',
    'hqwebapp/js/select2_knockout_bindings.ko',
], function (
    $,
    ko,
    _,
    initialPageData,
    privileges
) {
    var component = {
        viewModel: function (params) {
            var self = this;

            self.caseTypeObservable = params.caseTypeObservable;
            self.valueObservable = params.valueObservable;
            self.disabled = initialPageData.get('read_only_mode') || false;

            if ('allCaseProperties' in params) {
                self.allCaseProperties = params.allCaseProperties;
            } else {
                self.allCaseProperties = ko.observable(initialPageData.get("all_case_properties"));
            }
            self.casePropertyNames = ko.computed(function () {
                if (!self.allCaseProperties()) {
                    return [];
                }
                return self.allCaseProperties()[self.caseTypeObservable()] || [];
            });

            self.showDropdown = privileges.hasPrivilege('data_dictionary');
            self.placeholder = gettext("case property name");
        },
        template: '<div>\
          <!-- ko if: showDropdown -->\
            <select class="form-control"\
                    required\
                    data-bind="value: valueObservable, autocompleteSelect2: casePropertyNames"\
            ></select>\
          <!-- /ko -->\
          <!-- ko ifnot: showDropdown -->\
          <input type="text"\
                 required\
                 class="textinput form-control"\
                 data-bind="value: valueObservable, disable: disabled,\
                 attr: { placeholder: placeholder }"\
          />\
          <!-- /ko -->\
        </div>',
    };

    var register = function () {
        ko.components.register("case-property-input", component);
    };

    return {
        register: register,
    };
});
