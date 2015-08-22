ko.subscribable.fn.snakeCase = function(re) {
    // Converts non-word characters to snake case
    // this.my_thing = ko.observable('hi there').snakeCase()
    // -> hi_there
    re = re || /\W+/g;
    return ko.computed({
        read: function() {
            return this().replace(re, '_');
        },
        write: function(value) {
            this(value.replace(re, '_'));
            this.valueHasMutated();
        },
        owner: this
    }).extend({ notify: 'always' });
};
