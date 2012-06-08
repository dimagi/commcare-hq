/*jslint white: true, onevar: true, undef: true, newcap: true, maxerr: 50, indent: 4 */
// f returns the value by which an object is to be sorted
// f can either take the object as its only parameter
// or refer to the object as <code>this</code>
// Examples :
// numbers.sortBy(Math.abs);
// people.sortBy(function () { return this.first_name; });
if (Array.prototype.sortBy === undefined) {
    Array.prototype.sortBy = function (f) {
        var compare = function (a, b) {
            var fa = f.apply(a, [a]),
                fb = f.apply(b, [b]);
            if (fa === fb) {
                return 0;
            } else {
                return fa > fb ? 1 : -1;
            }
        };
        this.sort(compare);
    };
}