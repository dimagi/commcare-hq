ko.components.register('inline-edit', {
    viewModel: function(params) {
        var self = this;
        self.name = params.name || '';
        self.original = (ko.isObservable(params.value) ? params.value() : params.value) || '';
        self.id = params.id || '';
        self.rows = params.rows || 2;
        self.value = ko.isObservable(params.value) ? params.value : ko.observable(self.original);
        self.editing = ko.observable(false);
        self.saveHasFocus = ko.observable(false);
        self.cancelHasFocus = ko.observable(false);

        self.edit = function() {
            self.editing(true);
        };

        self.save = function() {
            self.original = self.value();
            self.editing(false);
        };

        self.cancel = function() {
            self.value(self.original);
            self.editing(false);
        };

        self.blur = function() {
            setTimeout(function() {
                if (!self.saveHasFocus() && !self.cancelHasFocus()) {
                    self.editing(false);
                    self.cancel();
                }
            }, 200);
        };
    },
    template:
        '<div class="ko-inline-edit">\
            <div class="read-only" data-bind="visible: !editing(), click: edit">\
                <i class="fa fa-pencil pull-right"></i>\
                <span class="text" data-bind="text: value"></span>\
            </div>\
            <div class="read-write" data-bind="visible: editing()">\
                <div class="form-group">\
                    <textarea class="form-control" data-bind="\
                        attr: {name: name, id: id, rows: rows},\
                        value: value, hasFocus: editing(),\
                        event: {blur: blur},\
                    "></textarea>\
                </div>\
                <div class="form-group">\
                    <button class="btn btn-success" data-bind="click: save, hasFocus: saveHasFocus">\
                        <i class="fa fa-check"></i>\
                    </button>\
                    <button class="btn btn-danger" data-bind="click: cancel, hasFocus: cancelHasFocus">\
                        <i class="fa fa-remove"></i>\
                    </button>\
                </div>\
            </div>\
        </div>',
});

$(document).ready(function() {
    _.each($("inline-edit"), function(widget) {
        $(widget).koApplyBindings();
    });
});
