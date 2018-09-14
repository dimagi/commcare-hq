/*
 * Component for an inline editing widget: a piece of text that, when clicked on, turns into an input (textarea or
 * text input). The input is accompanied by a save button capable of saving the new value to the server via ajax.
 *
 * Optional parameters
 *  - url: The URL to call on save. If none is given, no ajax call will be made
 *  - value: Text to display and edit
 *  - name: HTML name of input
 *  - id: HTML id of input
 *  - placeholder: Text to display when in read-only mode if value is blank
 *  - lang: Display this language code in a badge next to the widget.
 *  - nodeName: 'textarea' or 'input'. Defaults to 'textarea'.
 *  - rows: Number of rows in input.
 *  - cols: Number of cols in input.
 *  - saveValueName: Name to associate with text value when saving. Defaults to 'value'.
 *  - saveParams: Any additional data to pass along. May contain observables.
 *  - errorMessage: Message to display if server returns an error.
 */

hqDefine('hqwebapp/js/components/inline_edit', [
    'jquery',
    'knockout',
    'underscore',
    'DOMPurify/dist/purify.min',
], function (
    $,
    ko,
    _,
    DOMPurify
) {
    return {
        viewModel: function (params) {
            var self = this;

            // Attributes passed on to the input
            self.name = params.name || '';
            self.id = params.id || '';

            // Data
            self.placeholder = params.placeholder || '';
            self.readOnlyValue = (ko.isObservable(params.value) ? params.value() : params.value) || '';
            self.serverValue = self.readOnlyValue;
            self.value = ko.isObservable(params.value) ? params.value : ko.observable(self.readOnlyValue);
            self.lang = params.lang || '';

            // Styling
            self.nodeName = params.nodeName || 'textarea';
            self.rows = params.rows || 2;
            self.cols = params.cols || "";
            self.readOnlyClass = params.readOnlyClass || '';
            self.readOnlyAttrs = params.readOnlyAttrs || {};
            self.iconClass = ko.observable(params.iconClass);
            self.containerClass = params.containerClass || '';

            // Interaction: determine whether widget is in read or write mode
            self.isEditing = ko.observable(false);
            self.saveHasFocus = ko.observable(false);
            self.cancelHasFocus = ko.observable(false);
            self.afterRenderFunc = params.afterRenderFunc;

            // Save to server
            self.url = params.url;
            self.errorMessage = params.errorMessage || gettext("Error saving, please try again.");
            self.saveParams = ko.utils.unwrapObservable(params.saveParams) || {};
            self.saveValueName = params.saveValueName || 'value';
            self.hasError = ko.observable(false);
            self.isSaving = ko.observable(false);
            self.postSave = params.postSave;

            // On edit, set editing mode, which controls visibility of inner components
            self.edit = function () {
                self.isEditing(true);
            };

            self.beforeUnload = function () {
                return gettext("You have unsaved changes.");
            };

            // Save to server
            // On button press, flip back to read-only mode and show a spinner.
            // On server success, just hide the spinner. On error, display error and go back to edit mode.
            self.save = function () {
                self.isEditing(false);

                if (self.url) {
                    // Nothing changed
                    if (self.readOnlyValue === self.value() && self.serverValue === self.value()) {
                        return;
                    }

                    // Strip HTML and then undo DOMPurify's HTML escaping
                    self.value($("<div/>").html(DOMPurify.sanitize(self.value())).text());
                    self.readOnlyValue = self.value();

                    var data = self.saveParams;
                    _.each(data, function (value, key) {
                        data[key] = ko.utils.unwrapObservable(value);
                    });
                    data[self.saveValueName] = self.value();
                    self.isSaving(true);
                    $(window).on("beforeunload", self.beforeUnload);

                    $.ajax({
                        url: self.url,
                        type: 'POST',
                        dataType: 'JSON',
                        data: data,
                        success: function (data) {
                            self.isSaving(false);
                            self.hasError(false);
                            self.serverValue = self.readOnlyValue;
                            if (self.postSave) {
                                self.postSave(data);
                            }
                            $(window).off("beforeunload", self.beforeUnload);
                        },
                        error: function () {
                            self.isEditing(true);
                            self.isSaving(false);
                            self.hasError(true);
                            $(window).off("beforeunload", self.beforeUnload);
                        },
                    });
                }
            };

            // Revert to last value and switch modes
            self.cancel = function () {
                self.readOnlyValue = self.serverValue;
                self.value(self.readOnlyValue);
                self.isEditing(false);
                self.hasError(false);
            };
        },
        template: '<div data-bind="template: { name: \'ko-inline-edit-template\' }"></div>',
    };
});
