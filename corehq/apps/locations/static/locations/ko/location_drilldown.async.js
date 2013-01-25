
function api_get_children(loc_uuid, callback) {
  var params = (loc_uuid ? {parent_id: loc_uuid} : {});
  $('#loc_ajax').show();
  $.getJSON(LOAD_LOCS_URL, params, function(allData) {
      $('#loc_ajax').hide();
      callback(allData.objects);
    });
}

function LocationSelectViewModel(default_caption, auto_drill, loc_filter) {
  var model = this;

  this.default_caption = default_caption || 'All';
  this.auto_drill = (auto_drill == null ? true : auto_drill);
  this.loc_filter = loc_filter || function(loc) { return true; };

  this.root = ko.observable();
  this.selected_path = ko.observableArray();

  // TODO this should reference location type settings for domain
  this.location_types = [
    {type: 'state', allowed_parents: [null]},
    {type: 'district', allowed_parents: ['state']},
    {type: 'block', allowed_parents: ['district']},
    {type: 'village', allowed_parents: ['block']},
    {type: 'outlet', allowed_parents: ['village', 'block']},
  ];

  // currently selected location in the tree (or null)
  this.selected_location = ko.computed(function() {
      for (var i = this.selected_path().length - 1; i >= 0; i--) {
        var loc = this.selected_path()[i];
        if (loc.selected_is_valid()) {
          return loc.selected_child();
        }
      }
      return null;
    }, this);
  // uuid of currently selected location (or null)
  this.selected_locid = ko.computed(function() {
      return this.selected_location() ? this.selected_location().uuid() : null;
    }, this);

  // add a new level of drill-down to the tree
  this.path_push = function(loc) {
    this.selected_path.push(loc);
    if (this.auto_drill && loc.num_children() == 1) {
      loc.selected_child(loc.get_child(0));
    }
  }

  // search for a location within the tree by uuid; return path to location if found
  this.find_loc = function(uuid, loc) {
    loc = loc || this.root();

    if (loc.uuid() == uuid) {
      return [loc];
    } else {
      var path = null;
      $.each(loc.children(), function(i, e) {
          var subpath = model.find_loc(uuid, e);
          if (subpath) {
            path = subpath;
            path.splice(0, 0, loc);
            return false;
          }
        });
      return path;
    }
  }

  // load location hierarchy and set initial path
  this.load = function(locs, selected) {
    this.root(new LocationModel({name: '_root', children: locs}, this));
    this.path_push(this.root());

    if (selected) {
      // this relies on the hierarchy of the selected location being pre-populated
      // in the initial locations set from the server (i.e., no location of the
      // pre-selected location's lineage is loaded asynchronously
      var sel_path = this.find_loc(selected);
      if (sel_path) {
        for (var i = 1; i < sel_path.length; i++) {
          sel_path[i - 1].selected_child(sel_path[i]);
        }
      }
    }
  }
}

function LocationModel(data, root, depth) {
  var loc = this;

  this.name = ko.observable();
  this.type = ko.observable();
  this.uuid = ko.observable();
  this.children = ko.observableArray();
  this.depth = depth || 0;
  this.children_loaded = false;
  
  this.display_name = ko.computed(function() {
      return this.name() == '_all' ? root.default_caption : this.name();
    }, this);

  this.selected_child = ko.observable();
  // when a location is selected, update the drill-down tree
  this.selected_child.subscribe(function(val) {
      if (val == null) {
        return;
      }

      var removed = root.selected_path.splice(val.depth, 99);
      $.each(removed, function(i, e) {
          // reset so dropdown for loc will default to 'all' if shown again
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
  }

  this.load = function(data) {
    this.name(data.name);
    this.type(data.location_type);
    this.uuid(data.uuid);
    if (data.children != null) {
      this.set_children(data.children);
    }
  }

  this.set_children = function(data) {
    var children = [];
    if (data) {
      children = _.sortBy(data, function(e) { return e.name; });

      //'all choices' meta-entry; annoying that we have to stuff this in
      //the children list, but all my attempts to make computed observables
      //based of children() caused infinite loops.
      children.splice(0, 0, {name: '_all'});
    }
    this.children($.map(children, function(e) {
        var child = new LocationModel(e, root, loc.depth + 1);
        return (child.filter() ? child : null);
      }));
    this.children_loaded = true;
  }

  this.load_children_async = function(callback) {
    api_get_children(this.uuid(), function(resp) {
        loc.set_children(resp);
        callback(loc);
      });
  }

  //warning: duplicate code with location_tree.async.js
  this.allowed_child_types = ko.computed(function() {
          var loc = this;
          var types = [];
          $.each(root.location_types, function(i, loc_type) {
                  $.each(loc_type.allowed_parents, function(i, parent_type) {
                          if (loc.type() == parent_type) {
                              types.push(loc_type.type);
                          }
                      });
              });
          return types;
      }, this);

  this.can_have_children = ko.computed(function() {
          return (this.allowed_child_types().length > 0);
      }, this);
  
  this.filter = function() {
      return this.name() == '_all' || root.loc_filter(this);
  }

  this.load(data);
}
