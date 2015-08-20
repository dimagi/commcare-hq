ko.subscribable.fn.snakeCase = function() {
    // Converts non-word characters to snake case
    // this.my_thing = ko.observable('hi there').snakeCase()
    // -> hi_there
    return ko.computed({
        read: function() {
            return this().replace(/\W+/g, '_');
        },
        write: function(value) {
            this(value.replace(/\W+/g, '_'));
            this.valueHasMutated();
        },
        owner: this
    }).extend({ notify: 'always' });
};
