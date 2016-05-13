describe("PropertyListItem Behavior", function () {

    var PropertyListItem = hqImport("userreports/js/builder_view_models.js").PropertyListItem;

    it("Validates display text", function () {
        var item = new PropertyListItem();
        assert.equal(item.displayText(), "");
        assert.isFalse(item.displayTextIsValid());

        item.inputBoundDisplayText("foo");
        assert.equal(item.displayText(), "foo");
        assert.isTrue(item.displayTextIsValid());
    });

    it("Updates displayText on property change", function () {
        var item = new PropertyListItem();
        item.property("foo");
        assert.equal(item.displayText(), "foo");
    });

    it ("Does not update displayText if user has edited it", function () {
        var item = new PropertyListItem();
        item.inputBoundDisplayText("foo");
        item.property("bar");
        assert.equal(item.displayText(), "foo");
    });

    it ("Updates displayText if user has cleared it", function () {
        var item = new PropertyListItem();
        item.inputBoundDisplayText("foo");
        item.property("bar");
        item.inputBoundDisplayText("");
        item.property("baz");
        assert.equal(item.displayText(), "baz");
    });
});
