import models from "userreports/js/builder_view_models";

describe("PropertyListItem Behavior", function () {

    var identityFunc = function (x) {return x;};
    var nullFunc = function () { return null; };

    it("Validates display text", function () {
        var item = models.propertyListItem(identityFunc, nullFunc, true);
        assert.equal(item.displayText(), "");
        assert.isFalse(item.displayTextIsValid());

        item.inputBoundDisplayText("foo");
        assert.equal(item.displayText(), "foo");
        assert.isTrue(item.displayTextIsValid());
    });

    it("Validates empty display text", function () {
        var item = models.propertyListItem(identityFunc, nullFunc, false);
        assert.equal(item.displayText(), "");
        assert.isTrue(item.displayTextIsValid());
    });

    it("Updates displayText on property change", function () {
        var item = models.propertyListItem(identityFunc, nullFunc);
        item.property("foo");
        assert.equal(item.displayText(), "foo");
    });

    it("Does not update displayText if user has edited it", function () {
        var item = models.propertyListItem(identityFunc, nullFunc);
        item.inputBoundDisplayText("foo");
        item.property("bar");
        assert.equal(item.displayText(), "foo");
    });

    it("Updates displayText if user has cleared it", function () {
        var item = models.propertyListItem(identityFunc, nullFunc);
        item.inputBoundDisplayText("foo");
        item.property("bar");
        item.inputBoundDisplayText("");
        item.property("baz");
        assert.equal(item.displayText(), "baz");
    });
});
