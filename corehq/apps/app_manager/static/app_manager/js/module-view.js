$(function () {
    var initial_page_data = hqImport('hqwebapp/js/initial_page_data.js').get;

    if ($('#case-list-form').length) {
        var CaseListForm = function (data, formOptions, allowed, now_allowed_reason) {
            var self = this,
                initialOption = data.form_id ? data.form_id : 'disabled',
                formSet = !!data.form_id,
                formMissing = formSet && !formOptions[data.form_id];

            self.toggleState = function(active) {
                active = active && allowed;
                $('#case_list_form-label').toggle(active);
                $('#case_list_media').toggle(active);
            };

            self.toggleMessage = function() {
                self.messageVisible(!self.messageVisible());
            };

            self.buildOptstr = function(extra) {
                self.caseListFormOptstr = _.map(formOptions, function (label, value) {
                    return {value: value, label: label};
                });
                if (extra) {
                    self.caseListFormOptstr.push({value: extra, label: gettext("Unknown Form (missing)")});
                }
            };

            self.allowed = allowed;
            self.now_allowed_reason = now_allowed_reason;
            self.formMissing = ko.observable(formMissing);
            self.messageVisible = ko.observable(false);
            self.caseListForm = ko.observable(data.form_id ? data.form_id : null);
            self.caseListFormProxy = ko.observable(initialOption);
            self.caseListFormDisplay = formOptions[initialOption];

            self.caseListFormProxy.subscribe(function (form_id) {
                var disabled = form_id === 'disabled' || !formOptions[form_id];
                self.caseListForm(disabled ? null : form_id);
                self.toggleState(!disabled);
            });

            if (formMissing) {
                var removeOld = self.caseListFormProxy.subscribe(function (oldValue) {
                    if (formMissing && oldValue === initialOption) {
                        // remove the missing form from the options once the user select a real form
                        self.buildOptstr();
                        removeOld.dispose();
                        self.formMissing(false);
                    }
                }, null, "beforeChange");
            }

            self.toggleState(formSet && !formMissing);
            self.buildOptstr(formMissing ? data.form_id : false);
        };
        var caseListForm = new CaseListForm(
            initial_page_data('case_list_form_options').form,
            initial_page_data('case_list_form_options').options,
            initial_page_data('case_list_form_not_allowed_reason').allow,
            initial_page_data('case_list_form_not_allowed_reason').message
        );
        $('#case-list-form').koApplyBindings(caseListForm);
        // Reset save button after bindings
        // see http://manage.dimagi.com/default.asp?145851
        var $form = $('#case-list-form').closest('form'),
            $button = $form.find('.save-button-holder').data('button');
        $button.setStateWhenReady('saved');
    }

    if (moduleType == 'shadow') {
        var ShadowModule = hqImport('app_manager/js/shadow-module-settings.js').ShadowModule,
            options = initial_page_data('shadow_module_options');
        $('#sourceModuleForms').koApplyBindings(new ShadowModule(
            options.modules,
            options.source_module_id,
            options.excluded_form_ids
        ));
    }

    $(function () {
        var setupValidation = hqImport('app_manager/js/app_manager.js').setupValidation;
        setupValidation(hqImport('hqwebapp/js/urllib.js').reverse('validate_module_for_build'));
    });
    $(function() {
        // show display style options only when module configured to show module and then forms
        var $menu_mode = $('#put_in_root');
        var $display_style_container = $('#display_style_container');
        var update_display_view = function() {
            if($menu_mode.val() == 'false') {
                $display_style_container.show();
            } else {
                $display_style_container.hide();
            }
        }
        update_display_view()
        $menu_mode.on('change', update_display_view)
    });
});
