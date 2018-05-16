/**
 *  Handles fixtures' "Manage Tables" page.
 */
hqDefine("fixtures/js/lookup-manage", [
    "jquery",
    "knockout",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/hq.helpers",
    "hqwebapp/js/knockout_bindings.ko",
], function(
    $,
    ko,
    initialPageData
) {
    "use strict";
    var somethingWentWrong = $("#FailText").text();

    function log(x) {
        return x;
    }

    function makeEditable(o) {
        o.saveState = ko.observable('saved');
        o.editing = ko.observable(false);
        o.startEditing = function() {
            o.editing(true);
            try {
                o._backup = o.serialize();
            } catch (e) {

            }
        };
        o.stopEdit = function() {
            o.editing(false);
        };
        o.cancelEdit = function() {
            o.editing(false);
            o.cancel();
        };
        o.saveEdit = function() {
            o.editing(false);
            log(o);
            o.save();
        };
        return o;
    }

    function makeDataType(o, app) {
        var self = ko.mapping.fromJS(o),
            raw_fields = self.fields();
        self.original_tag = self.tag();
        self.original_visibility = self.is_global();
        self.isVisible = ko.observable(true);
        self.fields = ko.observableArray([]);
        makeEditable(self);
        if (!o._id) {
            self._id = ko.observable();
        }
        self.view_link = ko.computed(function() {
            return initialPageData.reverse('fixture_interface_dispatcher') + "?table_id=" + self._id();
        }, self);
        self.aboutToDelete = ko.observable(false);
        self.addField = function(data, event, o) {
            var i, field;
            if (o) {
                field = {
                    tag: ko.observable(o.tag),
                    with_props: ko.observable(o.with_props),
                    original_tag: ko.observable(o.tag),
                    is_new: ko.observable(false),
                    remove: ko.observable(false),
                    editing: ko.observable(false),
                };
            } else {
                field = {
                    tag: ko.observable(""),
                    with_props: ko.observable(false),
                    original_tag: ko.observable(""),
                    is_new: ko.observable(true),
                    remove: ko.observable(false),
                    editing: ko.observable(true),
                };
            }
            field.isDuplicate = ko.computed(function() {
                var j, noRepeats = true;
                var curVal = field.tag();
                for (j = 0; j < self.fields().length; j += 1) {
                    var thatField = self.fields()[j];
                    if (thatField !== field && thatField.tag() === curVal) {
                        noRepeats = false;
                    }
                }
                return !noRepeats;
            });
            field.isBadSlug = ko.computed(function() {
                var patt = new RegExp("([/\\<> ])");
                return patt.test(field.tag());
            });
            field.noXMLStart = ko.computed(function() {
                var curVal = field.tag();
                return curVal.startsWith('xml');
            });
            field.remove_if_new = function() {
                if (field.is_new() == true) {
                    self.fields.remove(field);
                }
            };
            self.fields.push(field);
        };
        for (var i = 0; i < raw_fields.length; i += 1) {
            var tag = raw_fields[i].field_name();
            var with_props = !!raw_fields[i].properties().length;
            self.addField(undefined, undefined, {
                tag: tag,
                with_props: with_props,
            });
        }

        self.save = function() {
            $.ajax({
                type: self._id() ? (self._destroy ? 'delete' : 'put') : 'post',
                url: initialPageData.reverse('update_lookup_tables') + (self._id() || ''),
                data: JSON.stringify(self.serialize()),
                dataType: 'json',
                error: function(data) {
                    var error_message;
                    if (data.responseText == "DuplicateFixture") {
                        error_message = "Can not create table with ID '" + self.tag() + "'. Table IDs should be unique.";
                    } else {
                        error_message = somethingWentWrong;
                    }
                    $("#FailText").text(error_message);
                    $("#editFailure").removeClass('hide');
                    self.cancel();
                    self.saveState('saved');
                },
                success: function(data) {
                    if (data.validation_errors) {
                        var $failMsg = $("<p />").text(data.error_msg);
                        var $failList = $("<ul />");
                        for (var v = 0; v < data.validation_errors.length; v++) {
                            $failList.append($("<li />").text(data.validation_errors[v]));
                        }
                        $("#FailText")
                            .text('')
                            .append($failMsg)
                            .append($failList);
                        $("#editFailure").removeClass('hide');
                        self.cancel();
                        self.saveState('saved');
                        return;
                    }
                    self.saveState('saved');
                    if (!self._id()) {
                        self._id(data._id);
                    }
                    self.original_visibility = self.is_global();
                    self.original_tag = self.tag();
                    var keptFields = [];
                    for (var i = 0; i < self.fields().length; i += 1) {
                        var field = self.fields()[i];
                        if (!field.remove()) {
                            field.original_tag(field.tag());
                            field.is_new(false);
                            keptFields.push(field);
                        }
                    }
                    self.fields(keptFields);
                },
            });
            self.saveState('saving');
        };
        self.cancel = function() {
            var indicesToRemoveAt = [];
            self.tag(self.original_tag);
            self.is_global(self.original_visibility);
            if (!self._id()) {
                self.isVisible(false);
                app.removeBadDataType(self);
            } else {
                for (var i = 0; i < self.fields().length; i += 1) {
                    var field = self.fields()[i];
                    if (field.is_new() === true) {
                        indicesToRemoveAt.push(i);
                        continue;
                    }
                    field.tag(field.original_tag());
                    field.remove(false);
                }
                for (var j = 0; j < indicesToRemoveAt.length; j += 1) {
                    var index = indicesToRemoveAt[j];
                    self.fields.remove(self.fields()[index]);
                }
            }
        };
        self.serialize = function() {
            return log({
                _id: self._id(),
                tag: self.tag(),
                view_link: self.view_link(),
                is_global: self.is_global(),
                fields: (function() {
                    var fields = {},
                        i;
                    for (i = 0; i < self.fields().length; i += 1) {
                        var field = self.fields()[i];
                        var patch;
                        if (field.is_new() == true) {
                            if (field.remove() == true) continue;
                            patch = {
                                "is_new": 1,
                            };
                            fields[field.tag()] = patch;
                        } else if (field.remove() === true) {
                            patch = {
                                "remove": 1,
                            };
                            fields[field.original_tag()] = patch;
                        } else if (field.tag() !== field.original_tag()) {
                            patch = {
                                "update": field.tag(),
                            };
                            fields[field.original_tag()] = patch;
                        } else {
                            patch = {};
                            fields[field.tag()] = patch;
                        }
                    }
                    return fields;
                }()),
            });
        };
        return self;
    }

    function appModel() {
        var self = {};
        self.data_types = ko.observableArray([]);
        self.loading = ko.observable(0);
        self.file = ko.observable();
        self.selectedTables = ko.observableArray([]);

        self.removeBadDataType = function(dataType) {
            setTimeout(function() {
                // This needs to be here otherwise if you remove the dataType
                // directly from the dataType, the DOM freezes and the page
                // can't scroll.
                self.data_types.remove(dataType);
            }, 1000);
        };

        self.updateSelectedTables = function(element, event) {
            var $elem = $(event.srcElement || event.currentTarget);
            var $checkboxes = $(".select-bulk");
            if ($elem.hasClass("toggle")) {
                self.selectedTables.removeAll();
                if ($elem.data("all")) {
                    $.each($checkboxes, function() {
                        $(this).prop("checked", true);
                        self.selectedTables.push(this.value);
                    });
                } else {
                    $.each($checkboxes, function() {
                        $(this).prop("checked", false);
                    });
                }
            }
            if ($elem.hasClass("select-bulk")) {
                var table_id = $elem[0].value;
                if ($elem[0].checked) {
                    self.selectedTables.push(table_id);
                } else {
                    self.selectedTables.splice(self.selectedTables().indexOf(table_id), 1);
                }
            }
        };

        self.downloadExcels = function(element, event) {
            var tables = [];
            if (self.selectedTables().length < 1)
                return;
            for (var i in self.selectedTables()) {
                tables.push(self.selectedTables()[i]);
            }
            $("#fixture-download").modal();
            if (tables.length > 0) {
                // POST, because a long querystring can overflow the request
                $.ajax({
                    url: initialPageData.reverse('download_fixtures'),
                    type: 'POST',
                    data: {
                        'table_ids': tables,
                    },
                    dataType: 'json',
                    success: function(response) {
                        self.setupDownload(response);
                    },
                    error: function(response) {
                        self.downloadError();
                    },
                });
            }
        };

        self.setupDownload = function(response) {
            var keep_polling = true;

            function poll() {
                if (keep_polling) {
                    $.ajax({
                        url: response.download_url,
                        dataType: 'text',
                        success: function(resp) {
                            var progress = $("#download-progress");
                            if (resp.replace(/[ \t\n]/g, '')) {
                                $("#downloading").addClass('hide');
                                progress.removeClass('hide').html(resp);
                                if (progress.find(".alert-success").length) {
                                    keep_polling = false;
                                }
                            }
                            if (keep_polling) {
                                setTimeout(poll, 2000);
                            }
                        },
                        error: function() {
                            self.downloadError();
                            keep_polling = false;
                        },
                    });
                }
            }
            $("#fixture-download").on("hide.bs.modal", function() {
                // stop polling if dialog is closed
                keep_polling = false;
            });
            $("#download-progress").addClass('hide');
            $("#downloading").removeClass('hide');
            poll();
        };

        self.downloadError = function() {
            var error_message = gettext("Sorry, something went wrong with the download. If you see this repeatedly please report an issue.");
            $("#fixture-download").modal("hide");
            $("#FailText").text(error_message);
            $("#editFailure").removeClass('hide');
        };

        self.addDataType = function() {
            var dataType = makeDataType({
                tag: "",
                fields: ko.observableArray([]),
                is_global: true,
            }, self);
            dataType.editing(true);
            self.data_types.push(dataType);
        };
        self.removeDataType = function(dataType) {
            if (confirm("Are you sure you want to delete the table '" + dataType.tag() + "'?")) {
                self.data_types.destroy(dataType);
                dataType.save();
            }
            return false;
        };
        self.loadData = function() {
            self.loading(self.loading() + 3);
            $.ajax({
                url: initialPageData.reverse('fixture_data_types'),
                type: 'get',
                dataType: 'json',
                success: function(data) {
                    var dataType;
                    for (var i = 0; i < data.length; i += 1) {
                        self.data_types.push(makeDataType(data[i], self));
                        dataType = self.data_types()[i];
                    }
                    self.loading(self.loading() - 1);
                },
            });
        };

        return self;
    }

    var el = $('#fixtures-ui');
    var app = appModel();
    el.koApplyBindings(app);
    el.removeClass('hide');
    app.loadData();
    $('#fixture-upload').koApplyBindings(app);
    $("#fixture-download").on("hidden.bs.modal", function() {
        $("#downloading").removeClass('hide');
        $("#download-progress").addClass('hide');
        $("#download-complete").addClass('hide');
    });
    $('.alert .close').on("click", function(e) {
        $(this).parent().addClass('hide');
    });
});
