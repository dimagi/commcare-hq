function IntrahealthLocViewModel(hierarchy) {
    LocationSelectViewModel.apply(this, [hierarchy]);

    this.load = function(locs, selected, restriction) {
      this.root(new IntrahealthLocModel({name: '_root', children: locs, 'restriction': restriction}, this));
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

function IntrahealthLocModel(data, root, depth) {
    var loc = this;
    LocationModel.apply(this, [data, root, depth]);

    this.set_children = function(data) {
      var children = [];
      if (data) {
        children = _.sortBy(data, function(e) { return e.name; });

        //'all choices' meta-entry; annoying that we have to stuff this in
        //the children list, but all my attempts to make computed observables
        //based of children() caused infinite loops.
        if (this.depth > REQUIRED) {
            children.splice(0, 0, {name: '_all'});
        }
      }

      this.children($.map(children, function(e) {
          var child = new IntrahealthLocModel(e, root, loc.depth + 1);
          return (child.filter() ? child : null);
        }));
      loc.children_loaded = true;
    };

  this.load_children_async = function(callback) {
    if (this.depth < root.location_types.length) {
        api_get_children(this.uuid(), function (resp) {
            loc.set_children(resp);
            callback(loc);
        });
    }
  };
  this.load(data);
}