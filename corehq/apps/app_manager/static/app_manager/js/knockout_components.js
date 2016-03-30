ko.components.register('inline-edit', {
    viewModel: function(params) {
        var self = this;
        self.name = params.name;
        self.original = params.value;
        self.rows = params.rows || 2;
        self.value = ko.observable(self.original);
        self.editing = ko.observable(false);

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
                self.editing(false);
                self.cancel();
            }, 200);
        };
    },
    template:
        '<div class="ko-inline-edit">\
            <div class="read-only" data-bind="visible: !editing(), click: edit">\
                <span data-bind="text: value"></span>\
                <i class="fa fa-pencil"></i>\
            </div>\
            <div class="read-write" data-bind="visible: !editing()">\
<div class="col-sm-6">\
                <textarea class="form-control" data-bind="\
                    attr: {name: name, rows: rows},\
                    value: value, hasFocus: editing(),\
                    event: {blur: blur},\
                "></textarea>\
</div>\
<div class="col-sm-6">\
                <button class="btn btn-success" data-bind="click: save">\
                    <i class="fa fa-check"></i>\
                </button>\
                <button class="btn btn-danger" data-bind="click: cancel">\
                    <i class="fa fa-remove"></i>\
                </button>\
            </div>\
</div>\
        </div>',
});

$(document).ready(function() {
    $("inline-edit").koApplyBindings();
});
