ko.bindingHandlers.clickable = (function () {
    function Clickable() {
        var self = this;
        self.init = function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
            $(element).css({cursor: 'pointer'});
            return Clickable.prototype.init(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
        }
    }
    Clickable.prototype = ko.bindingHandlers.click;
    return new Clickable();
}());

$(function () {
    var el = $('#fixtures-ui');
    function log (x) {
        console.log(x);
        return x;
    }
    function makeEditable(o) {
        o.saveState = ko.observable('saved');
        o.editing = ko.observable(false);
        o.startEditing = function () {
            o.editing(true);
            try {
                o._backup = o.serialize();
            } catch (e) {

            }
        };
        o.stopEdit = function () {
            o.editing(false);
        };
        o.cancelEdit = function () {
            o.editing(false);
            o.cancel();
        };
        o.saveEdit = function () {
            o.editing(false);
            o.save();
        };
        return o;
    }
    function makeDataType(o, app) {
        var self = ko.mapping.fromJS(o),
            raw_fields = self.fields();
        self.fields = ko.observableArray([]);
        self.data_items = ko.observableArray([]);
        makeEditable(self);
        if (!o._id) {
            self._id = ko.observable();
        }
        self.aboutToDelete = ko.observable(false);
        self.addField = function (data, event, o) {
            var i, field;
            if (o) {
                field = {
                    tag: ko.observable(o.tag),
                    editing: ko.observable(false)
                };
            } else {
                field = {
                    tag: ko.observable(""),
                    editing: ko.observable(true)
                };
            }
            field.editTag = ko.computed({
                read: function () {
                    return field.tag();
                },
                write: function (tag) {
                    var j, noRepeats = true;
                    for (j = 0; j < self.fields().length; j += 1) {
                        if (self.fields()[j].tag === tag) {
                            noRepeats = false;
                        }
                    }
                    if (noRepeats) {
                        var oldTag = field.tag;
                        field.tag(tag);
                    }
                    // all the items have a pointer to this field, so the tag name changes automatically
                    // but they still need to be saved
                    for (j = 0; j < self.data_items().length; j += 1) {
                        self.data_items()[i].save();
                    }
                }
            });
            self.fields.push(field);
            for (i = 0; i < self.data_items().length; i += 1) {
                self.data_items()[i].fields.push({value: ko.observable(""), tag: field.tag});
            }
        };
        self.removeField = function (field) {
            var i,
                index = self.fields.indexOf(field),
                itemFields;
            self.fields.remove(field);
            for (i = 0; i < self.data_items().length; i += 1) {
                itemFields = self.data_items()[i].fields;
                itemFields.remove(itemFields()[index]);
            }
        };
        for (var i = 0; i < raw_fields.length; i += 1) {
            self.addField(undefined, undefined, {tag: raw_fields[i]});
        }

        self.save = function () {
            $.ajax({
                type: self._id() ? (self._destroy ? 'delete' : 'put') : 'post',
                url: 'data-types/' + (self._id() || ''),
                data: JSON.stringify(self.serialize()),
                dataType: 'json',
                success: function (data) {
                    self.saveState('saved');
                    if (!self._id()) {
                        self._id(data._id)
                    }
                }
            });
            self.saveState('saving');
        };
        self.serialize = function () {
            return log({
                _id: self._id(),
                name: self.name(),
                tag: self.tag(),
                fields: (function () {
                    var fields = [], i;
                    for (i = 0; i < self.fields().length; i += 1) {
                        fields.push(self.fields()[i].tag());
                    }
                    return fields;
                }())
            });
        };
        return self;
    }
    function App() {
        var self = this;
        self.data_types = ko.observableArray([]);
        self.loading = ko.observable(0);
        self.selectedTables = ko.observableArray([]);

        self.updateSelectedTables = function(element, event) {
            var $elem = $(event.srcElement || event.currentTarget);
            var $checkboxes = $(".select-bulk");
            if ($elem.hasClass("toggle")){
                self.selectedTables.removeAll();
                if ($elem.data("all")) {
                    $.each($checkboxes, function() {
                        $(this).attr("checked", true);
                        self.selectedTables.push(this.value); 
                    });
                }
                else {
                    $.each($checkboxes, function() {
                        $(this).attr("checked", false);
                    });
                }
            }
            if ($elem.hasClass("select-bulk")) {
                var table_id = $elem[0].value;
                if ($elem[0].checked) {
                    self.selectedTables.push(table_id);
                }
                else {
                    self.selectedTables.splice(self.selectedTables().indexOf(table_id), 1);
                }
            }
        };

        self.downloadExcels = function(element, event) {
            var tables = [];
            var FixtureUrl = FixtureDownloadUrl;
            for (var i in self.selectedTables()) {
                tables.push(self.selectedTables()[i]);
                FixtureUrl = FixtureUrl + "table_id="+self.selectedTables()[i]+"&";
            }
            $("#fixture-download").modal();
            if (tables.length > 0){
                $.ajax({
                    url: FixtureUrl,
                    dataType: 'json',
                }).success(function (response) {
                    $("#downloading").hide();
                    $("#download-complete").show();
                    $("#file-download-url").attr("href", FixtureFileDownloadUrl+"path="+response.path);
                    console.log(response);
                });
            }
            
        };

        self.addDataType = function () {
            var dataType = makeDataType({
                name: "",
                tag: "",
                fields: ko.observableArray([])
            }, self);
            dataType.editing(true);
            self.data_types.push(dataType);
        };
        self.removeDataType = function (dataType) {
            self.data_types.destroy(dataType);
            dataType.save();
        };
        self.loadData = function () {
            self.loading(self.loading() + 3);
            $.ajax({
                url: 'data-types/',
                type: 'get',
                dataType: 'json',
                success: function (data) {
                    var dataType;
                    for (var i = 0; i < data.length; i += 1) {
                        self.data_types.push(makeDataType(data[i], self));
                        dataType = self.data_types()[i];
                    }
                    self.loading(self.loading() - 1)
                }
            });
        };
    }
    function FileUpload() {
                this.file = ko.observable();
    }
    var app = new App();
    ko.applyBindings(app, el.get(0));
    ko.applyBindings(new FileUpload(), $('#fixture-upload')[0]);
    el.show();
    app.loadData();
    $("#fixture-download").on("hidden", function(){
                    $("#downloading").show();
                    $("#download-complete").hide();
    });
});