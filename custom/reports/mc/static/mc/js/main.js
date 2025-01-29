hqDefine("mc/js/main", [
    'jquery',
    'knockout',
    'underscore',
    'commcarehq',
], function (
    $,
    ko,
    _
) {
    function api_get_children(fdi_uuid, depth, callback) {
        var hierarchy = $("#mc-drillable-async").data("hierarchy");
        var params = (fdi_uuid ? {parent_id: fdi_uuid} : {});
        params["parent_ref_name"] = hierarchy[depth]["parent_ref"];
        params["child_type"] = hierarchy[depth]["id"];
        params["references"] = hierarchy[depth]["references"];
        $('#fdi_ajax').removeClass('hide');
        $.getJSON($("#mc-drillable-async").data("api-root"), params, function(allData) {
            $('#fdi_ajax').addClass('hide');
            callback(allData.objects);
        });
    };

    $(document).on("ajaxComplete", function (e, xhr, options) {
        var fragment = "async/",
            pageUrl = window.location.href.split('?')[0],
            ajaxUrl = options.url.split('?')[0];
        if (ajaxUrl.indexOf(fragment) === -1 || !pageUrl.endsWith(ajaxUrl.replace(fragment, ''))) {
            return;
        }
        var fdis = $("#mc-drillable-async").data("fdis");
        var selected = $("#mc-drillable-async").data("selected-fdi-id");

        var model = new FixtureSelectViewModel();
        $('#group_' + $("#mc-drillable-async").data("control-slug")).koApplyBindings(model);
        model.load(fdis, selected);

    });

    function FixtureSelectViewModel() {
        var model = this;
        var hierarchy = $("#mc-drillable-async").data("hierarchy");

        this.root = ko.observable();
        this.selected_path = ko.observableArray();

        // currently selected fixture in the tree (or null)
        this.selected_fixture = ko.computed(function() {
            for (var i = this.selected_path().length - 1; i >= 0; i--) {
                var fixt = this.selected_path()[i];
                if (fixt.selected_is_valid()) {
                    return fixt.selected_child();
                }
            }
            return null;
        }, this);

        // uuid of currently selected fixture (or null)
        this.selected_fixtid = ko.computed(function() {
            var sf = this.selected_fixture();
            if (sf) return hierarchy[sf.depth-1]["type"] + ":" + sf.uuid();
            else return null;
        }, this);

        // add a new level of drill-down to the tree
        this.path_push = function(fixt) {
            this.selected_path.push(fixt);
            if (fixt.num_children() == 1) {
                fixt.selected_child(fixt.get_child(0));
            }
        };

        // search for a fixture within the tree by uuid; return path to fixture if found
        this.find_fixt = function(uuid, fixt) {
            fixt = fixt || this.root();

            if (fixt.uuid() == uuid) {
                return [fixt];
            } else {
                var path = null;
                $.each(fixt.children(), function(i, e) {
                    var subpath = model.find_fixt(uuid, e);
                    if (subpath) {
                        path = subpath;
                        path.splice(0, 0, fixt);
                        return false;
                    }
                });
                return path;
            }
        };

        // load fixture hierarchy and set initial path
        this.load = function(fdis, selected) {
            this.root(new FixtureModel({name: '_root', fields: {}, children: fdis}, this));
            this.path_push(this.root());

            if (selected) {
                // this relies on the hierarchy of the selected fixture being pre-populated
                // in the initial fixtures set from the server (i.e., no fixture of the
                // pre-selected fixture's lineage is loaded asynchronously
                var sel_path = this.find_fixt(selected);
                if (sel_path) {
                    for (var i = 1; i < sel_path.length; i++) {
                        sel_path[i - 1].selected_child(sel_path[i]);
                    }
                }
            }
        };
    }

    function FixtureModel(data, root, depth) {
        var fixt = this;
        var hierarchy = $("#mc-drillable-async").data("hierarchy");

        this.name = ko.observable();
        this.type = ko.observable();
        this.uuid = ko.observable();
        this.children = ko.observableArray();
        this.depth = depth || 0;
        this.children_loaded = false;

        this.display_name = ko.computed(function() {
            return this.name() == '_all' ? 'All' : this.name();
        }, this);

        this.selected_child = ko.observable();
        // when a fixture is selected, update the drill-down tree
        this.selected_child.subscribe(function(val) {
            if (val == null || val.depth >= hierarchy.length) {
                return;
            }

            var removed = root.selected_path.splice(val.depth, 99);
            $.each(removed, function(i, e) {
                // reset so dropdown for fixt will default to 'all' if shown again
                e.selected_child(null);
            });

            var post_children_loaded = function(parent) {
                if (parent.num_children()) {
                    root.path_push(parent);
                }
            };

            if (val.uuid() != null && !val.children_loaded) {
                val.load_children_async(post_children_loaded);
            } else {
                post_children_loaded(val);
            }
        }, this);
        this.selected_is_valid = ko.computed(function() {
            return this.selected_child() && this.selected_child().name() != '_all';
        }, this);

        // helpers to account for the 'all' meta-entry
        this.num_children = ko.computed(function() {
            return (this.children().length == 0 ? 0 : this.children().length - 1);
        }, this);
        this.get_child = function(i) {
            return this.children()[i + 1];
        };

        this.load = function(data) {
            if (data.fields.name == '_all') this.name('_all');
            else if (this.depth > 0) this.name(data.fields[hierarchy[this.depth-1]["display"]] || null);
            this.type(data.fixture_type);
            this.uuid(data.id || null);
            if (data.children != null) {
                this.set_children(data.children);
            }
        };

        this.set_children = function(data) {
            var children = [];
            if (data) {
                children = _.sortBy(data, function(e) { return e.name; });

                //'all choices' meta-entry; annoying that we have to stuff this in
                //the children list, but all my attempts to make computed observables
                //based of children() caused infinite loops.
                children.splice(0, 0, {fields: {name: '_all'}});
            }
            this.children($.map(children, function(e) {
                return new FixtureModel(e, root, fixt.depth + 1);
            }));
            this.children_loaded = true;
        };

        this.load_children_async = function(callback) {
            api_get_children(this.uuid(), this.depth, function(resp) {
                fixt.set_children(resp);
                callback(fixt);
            });
        };

        this.load(data);
    }
});
