/*
 * Component for an inline editing widget: a piece of text that, when clicked on, turns into a textarea.
 *
 * Parameters (all optional)
 *  - value: Text to display and edit
 *  - name: HTML name of textarea
 *  - id: HTML id of textarea
 *  - placeholder: Text to display when in read-only mode if value is blank
 *  - inline: Whether or not to display widget in line with surrounding content. Defaults to false.
 *  - rows: Number of rows in textarea.
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
            self.value = ko.isObservable(params.value) ? params.value : ko.observable(self.original);

            // Styling
            self.inline = params.inline || false;
            self.rows = params.rows || 2;

            // Interaction: determine whether widget is in read or write mode
            self.editing = ko.observable(false);
            self.saveHasFocus = ko.observable(false);
            self.cancelHasFocus = ko.observable(false);

            // Save to server
            self.url = params.url;
            self.errorMessage = params.errorMessage || gettext("Error saving, please try again");
            self.saveParams = ko.utils.unwrapObservable(params.saveParams) || {};
            self.saveValueName = params.saveValueName || 'value';
            self.hasError = ko.observable(false);
            self.isSaving = ko.observable(false);

            // On edit, set editing mode, which controls visibility of inner components
            self.edit = function() {
                self.editing(true);
            };

            self.save = function() {
                // Client save: just store the value and switch modes
                self.original = self.value();
                self.editing(false);

                // Server save
                if (self.url) {
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
                        success: function (data) {
                            self.isSaving(false);
                            self.hasError(false);
                        },
                        error: function () {
                            //self.isSaving(false);
                            self.hasError(true);
                        }
                    });
                }
            };

            // Revert to last value and switch modes
            self.cancel = function() {
                self.value(self.original);
                self.editing(false);
            };

            // Revert to read-only mode on blur, without saving, unless the input
            // blurred only because focus jumped to one of the buttons (i.e., user pressed tab)
            self.blur = function() {
                setTimeout(function() {
                    if (!self.saveHasFocus() && !self.cancelHasFocus()) {
                        self.editing(false);
                        self.cancel();
                    }
                }, 200);
            };
        },
        template: '<div class="ko-inline-edit" data-bind="css: {inline: inline, \'has-error\': hasError()}">\
            <div class="read-only" data-bind="visible: !editing() && !hasError(), click: edit">\
                <i class="fa fa-pencil pull-right"></i>\
                <span class="text" data-bind="text: value"></span>\
                <span class="placeholder" data-bind="text: placeholder, visible: !value()"></span>\
            </div>\
            <div class="read-write" data-bind="visible: editing() || hasError(), css: {\'form-inline\': inline}">\
                <div class="form-group">\
                    <textarea class="form-control" data-bind="\
                        attr: {name: name, id: id, rows: rows},\
                        value: value, hasFocus: editing(),\
                        event: {blur: blur},\
                    "></textarea>\
                </div>\
                <div class="form-group">\
                    <button class="btn btn-success" data-bind="click: save, hasFocus: saveHasFocus, visible: !isSaving()">\
                        <i class="fa fa-check"></i>\
                    </button>\
                    <button class="btn btn-danger" data-bind="click: cancel, hasFocus: cancelHasFocus, visible: !isSaving() && !hasError()">\
                        <i class="fa fa-remove"></i>\
                    </button>\
                    <span data-bind="visible: isSaving()">\
                        <img src="/static/hqwebapp/img/ajax-loader.gif"/>\
                    </span>\
                </div>\
                <div class="help-block" data-bind="text: errorMessage, visible: hasError()"></div>\
            </div>\
        </div>',
    };
});

