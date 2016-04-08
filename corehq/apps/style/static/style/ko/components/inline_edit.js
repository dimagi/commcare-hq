/*
 * Component for an inline editing widget: a piece of text that, when clicked on, turns into a textarea.
 *
 * Parameters (all optional)
 *  - value: Text to display and edit
 *  - name: HTML name of textarea
 *  - id: HTML id of textarea
 *  - placeholder: Text to display when in read-only mode if value is blank
 *  - inline: Whether or not to display widget in line with surrounding content. Defaults to false.
 *  - lang: Display this language code in a badge next to the widget.
 *  - rows: Number of rows in textarea.
 *  - helpTitle: Title for help popover, if any.
 *  - helpContent: Content for help popover, if any.
 *
 * By default, the widget is client-side only, and it is up to the calling code to actually save the value
 * (likely by providing the widget with a name or id). The following parameters may be used to implement
 * a widget capable of saving to the server via ajax.
 *  - url: The URL to call on save.
 *  - saveValueName: Name to associate with text value when saving. Defaults to 'value'.
 *  - saveParams: Any additional data to pass along. May contain observables.
 *  - errorMessage: Message to display if server returns an error.
 */

hqDefine('style/ko/components/inline_edit.js', function() {
    return {
        viewModel: function(params) {
            var self = this;

            // Attributes passed on to the input
            self.name = params.name || '';
            self.id = params.id || '';

            // Data
            self.placeholder = params.placeholder || '';
            self.original = (ko.isObservable(params.value) ? params.value() : params.value) || '';
            self.serverValue = self.original;
            self.value = ko.isObservable(params.value) ? params.value : ko.observable(self.original);
            self.lang = params.lang || '';

            // Styling
            self.inline = params.inline || false;
            self.rows = params.rows || 2;
            self.readOnlyClass = params.readOnlyClass || '';
            self.helpTitle = params.helpTitle;
            self.helpContent = params.helpContent || self.helpTitle;

            // Interaction: determine whether widget is in read or write mode
            self.editing = ko.observable(false);
            self.saveHasFocus = ko.observable(false);
            self.cancelHasFocus = ko.observable(false);

            // Save to server
            self.url = params.url;
            self.errorMessage = params.errorMessage || gettext("Error saving, please try again.");
            self.saveParams = ko.utils.unwrapObservable(params.saveParams) || {};
            self.saveValueName = params.saveValueName || 'value';
            self.hasError = ko.observable(false);
            self.isSaving = ko.observable(false);

            // On edit, set editing mode, which controls visibility of inner components
            self.edit = function() {
                self.editing(true);
            };

            self.save = function() {
                self.editing(false);
                if (self.original === self.value() && (!self.url || self.serverValue === self.value())) {
                    return;
                }

                self.original = self.value();
                if (self.url) {
                    // Server save
                    var data = self.saveParams;
                    _.each(data, function(value, key) {
                        data[key] = ko.utils.unwrapObservable(value);
                    });
                    data[self.saveValueName] = self.value();
                    self.isSaving(true);
                    $.ajax({
                        url: self.url,
                        type: 'POST',
                        dataType: 'JSON',
                        data: data,
                        success: function (data) {  // eslint-disable-line no-unused-vars
                            self.isSaving(false);
                            self.hasError(false);
                            self.serverValue = self.original;
                        },
                        error: function () {
                            self.editing(true);
                            self.isSaving(false);
                            self.hasError(true);
                        }
                    });
                }
            };

            // Revert to last value and switch modes
            self.cancel = function() {
                self.original = self.serverValue;
                self.value(self.original);
                self.editing(false);
                self.hasError(false);
            };

            // Revert to read-only mode on blur, without saving, unless the input
            // blurred only because focus jumped to one of the buttons (i.e., user pressed tab)
            self.blur = function() {
                setTimeout(function() {
                    if (!self.saveHasFocus() && !self.cancelHasFocus() && !self.hasError()) {
                        self.editing(false);
                        self.value(self.original);
                    }
                }, 200);
            };
        },
        template: '<div class="ko-inline-edit" data-bind="css: {inline: inline, \'has-error\': hasError()}">\
            <!--ko if: helpTitle -->\
                <span class="pull-right">\
                    <span data-bind="makeHqHelp: {name: helpTitle, description: helpContent, format: \'html\', placement: \'left\'}"></span>\
                </span>\
            <!--/ko-->\
            <div class="read-only" data-bind="visible: !editing(), click: edit">\
                <i class="fa fa-pencil pull-right" data-bind="visible: !isSaving()"></i>\
                <span data-bind="visible: isSaving()" class="pull-right">\
                    <img src="/static/hqstyle/img/loading.gif"/>\
                </span>\
                <!-- ko if: lang -->\
                    <span class="btn btn-xs btn-info btn-langcode-preprocessed pull-right"\
                          data-bind="text: lang, visible: !value()"\
                    ></span>\
                <!-- /ko -->\
                <span class="text" data-bind="text: value, css: readOnlyClass"></span>\
                <span class="placeholder" data-bind="text: placeholder, visible: !value()"></span>\
            </div>\
            <div class="read-write" data-bind="visible: editing(), css: {\'form-inline\': inline}">\
                <div class="form-group">\
                    <textarea class="form-control langcode-container" data-bind="\
                        attr: {name: name, id: id, placeholder: placeholder, rows: rows},\
                        value: value,\
                        hasFocus: editing(),\
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
        </div>'
    };
});

