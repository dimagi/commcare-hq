/*
 * Component for an inline editing widget: a piece of text that, when clicked on, turns into a textarea.
 * The textarea is accompanied by a save button capable of saving the new value to the server via ajax.
 *
 * Required parameters
 *  - url: The URL to call on save.
 *
 * Optional parameters
 *  - value: Text to display and edit
 *  - name: HTML name of textarea
 *  - id: HTML id of textarea
 *  - placeholder: Text to display when in read-only mode if value is blank
 *  - inline: Whether or not to display widget in line with surrounding content. Defaults to false.
 *  - lang: Display this language code in a badge next to the widget.
 *  - rows: Number of rows in textarea.
 *  - saveValueName: Name to associate with text value when saving. Defaults to 'value'.
 *  - saveParams: Any additional data to pass along. May contain observables.
 *  - errorMessage: Message to display if server returns an error.
 */

hqDefine('style/ko/components/inline_edit.js', function() {
    return {
        viewModel: function(params) {
            var self = this;

            if (!params.url) {
                throw "Inline edit widget requires a url";
            }

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
            self.inline = params.inline || false;
            self.rows = params.rows || 2;
            self.readOnlyClass = params.readOnlyClass || '';

            // Interaction: determine whether widget is in read or write mode
            self.isEditing = ko.observable(false);
            self.saveHasFocus = ko.observable(false);
            self.cancelHasFocus = ko.observable(false);

            // Save to server
            self.url = params.url;
            self.errorMessage = params.errorMessage || gettext("Error saving, please try again.");
            self.saveParams = ko.utils.unwrapObservable(params.saveParams) || {};
            self.saveValueName = params.saveValueName || 'value';
            self.hasError = ko.observable(false);
            self.isSaving = ko.observable(false);
            self.postSave = params.postSave;

            // On edit, set editing mode, which controls visibility of inner components
            self.edit = function() {
                self.isEditing(true);
            };

            self.beforeUnload = function() {
                return "You have unsaved changes.";
            };

            // Save to server
            // On button press, flip back to read-only mode and show a spinner.
            // On server success, just hide the spinner. On error, display error and go back to edit mode.
            self.save = function() {
                self.isEditing(false);

                // Nothing changed
                if (self.readOnlyValue === self.value() && self.serverValue === self.value()) {
                    return;
                }

                self.readOnlyValue = self.value();
                var data = self.saveParams;
                _.each(data, function(value, key) {
                    data[key] = ko.utils.unwrapObservable(value);
                });
                data[self.saveValueName] = self.value();
                self.isSaving(true);
                $(window).bind("beforeunload", self.beforeUnload);

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
                        $(window).unbind("beforeunload", self.beforeUnload);
                    },
                    error: function () {
                        self.isEditing(true);
                        self.isSaving(false);
                        self.hasError(true);
                        $(window).unbind("beforeunload", self.beforeUnload);
                    },
                });
            };

            // Revert to last value and switch modes
            self.cancel = function() {
                self.readOnlyValue = self.serverValue;
                self.value(self.readOnlyValue);
                self.isEditing(false);
                self.hasError(false);
            };

            // Revert to read-only mode on blur, without saving, unless the input
            // blurred only because focus jumped to one of the buttons (i.e., user pressed tab)
            self.blur = function() {
                setTimeout(function() {
                    if (!self.saveHasFocus() && !self.cancelHasFocus() && !self.hasError()) {
                        self.isEditing(false);
                        self.value(self.readOnlyValue);
                    }
                }, 200);
            };
        },
        template: '<div class="ko-inline-edit" data-bind="css: {inline: inline, \'has-error\': hasError()}">\
            <div class="read-only" data-bind="visible: !isEditing(), click: edit">\
                <span data-bind="visible: isSaving()" class="pull-right">\
                    <img src="/static/hqstyle/img/loading.gif"/>\
                </span>\
                <!-- ko if: lang -->\
                    <span class="btn btn-xs btn-info btn-langcode-preprocessed pull-right"\
                          data-bind="text: lang, visible: !value()"\
                    ></span>\
                <!-- /ko -->\
                <span class="text" data-bind="text: value, css: readOnlyClass"></span>\
                <span class="placeholder" data-bind="text: placeholder, css: readOnlyClass, visible: !value()"></span>\
            </div>\
            <div class="read-write" data-bind="visible: isEditing(), css: {\'form-inline\': inline}">\
                <div class="form-group langcode-container">\
                    <textarea class="form-control" data-bind="\
                        attr: {name: name, id: id, placeholder: placeholder, rows: rows},\
                        value: value,\
                        hasFocus: isEditing(),\
                        event: {blur: blur},\
                    "></textarea>\
                    <!-- ko if: lang -->\
                        <span class="btn btn-xs btn-info btn-langcode-preprocessed langcode-input pull-right"\
                              data-bind="text: lang, visible: !value()"\
                        ></span>\
                    <!-- /ko -->\
                </div>\
                <div class="help-block" data-bind="text: errorMessage, visible: hasError()"></div>\
                <div class="form-group">\
                    <button class="btn btn-success" data-bind="click: save, hasFocus: saveHasFocus, visible: !isSaving()">\
                        <i class="fa fa-check"></i>\
                    </button>\
                    <button class="btn btn-danger" data-bind="click: cancel, hasFocus: cancelHasFocus, visible: !isSaving()">\
                        <i class="fa fa-remove"></i>\
                    </button>\
                </div>\
            </div>\
        </div>',
    };
});

