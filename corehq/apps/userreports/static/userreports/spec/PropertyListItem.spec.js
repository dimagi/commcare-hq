/* global describe, it */
describe("PropertyListItem Behavior", function () {

    var PropertyListItem = hqImport("userreports/js/builder_view_models.js").PropertyListItem;
    var identityFunc = function (x) {return x;};
    var nullFunc = function (x) { return null; };

    it("Validates display text", function () {
        var item = new PropertyListItem(identityFunc, nullFunc, true);
        assert.equal(item.displayText(), "");
        assert.isFalse(item.displayTextIsValid());

        item.inputBoundDisplayText("foo");
        assert.equal(item.displayText(), "foo");
        assert.isTrue(item.displayTextIsValid());
    });

    it("Validates empty display text", function () {
        var item = new PropertyListItem(identityFunc, nullFunc, false);
        assert.equal(item.displayText(), "");
        assert.isTrue(item.displayTextIsValid());
    });

    it("Updates displayText on property change", function () {
        var item = new PropertyListItem(identityFunc, nullFunc);
        item.property("foo");
        assert.equal(item.displayText(), "foo");
    });

    it ("Does not update displayText if user has edited it", function () {
        var item = new PropertyListItem(identityFunc, nullFunc);
        item.inputBoundDisplayText("foo");
        item.property("bar");
        assert.equal(item.displayText(), "foo");
    });

    it ("Updates displayText if user has cleared it", function () {
        var item = new PropertyListItem(identityFunc, nullFunc);
        item.inputBoundDisplayText("foo");
        item.property("bar");
        item.inputBoundDisplayText("");
        item.property("baz");
        assert.equal(item.displayText(), "baz");
    });
});
