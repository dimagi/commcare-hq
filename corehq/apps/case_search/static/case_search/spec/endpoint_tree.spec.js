import {
    subtreeGroupHeight,
    cloneWithNewIds,
    normalizeRoot,
} from "case_search/js/endpoint_tree";

const component = (extra = {}) => ({ type: "component", ...extra });
const group = (type, children) => ({ type, children });

describe("endpoint_tree", function () {
    describe("subtreeGroupHeight", function () {
        it("is 0 for a component", function () {
            assert.equal(subtreeGroupHeight(component()), 0);
        });

        it("is 1 for a group of only components", function () {
            assert.equal(
                subtreeGroupHeight(group("all", [component(), component()])),
                1,
            );
        });

        it("is 1 for an empty group", function () {
            assert.equal(subtreeGroupHeight(group("any", [])), 1);
        });

        it("is 1 for a group with no children key", function () {
            assert.equal(subtreeGroupHeight({ type: "all" }), 1);
        });

        it("counts the deepest nested group", function () {
            const tree = group("all", [
                component(),
                group("any", [component()]),
            ]);
            assert.equal(subtreeGroupHeight(tree), 2);
        });

        it("follows the deepest branch, not the first", function () {
            const tree = group("all", [
                group("any", [component()]),
                group("none", [group("all", [component()])]),
            ]);
            assert.equal(subtreeGroupHeight(tree), 3);
        });
    });

    describe("cloneWithNewIds", function () {
        it("deep-clones so the source is not shared", function () {
            const source = group("all", [component({ field: "name" })]);
            const { node: clone } = cloneWithNewIds(source, 1);
            clone.children[0].field = "changed";
            assert.equal(source.children[0].field, "name");
        });

        it("assigns sequential ids pre-order starting at nextId", function () {
            const source = group("all", [
                component(),
                group("any", [component()]),
            ]);
            const { node: clone } = cloneWithNewIds(source, 10);
            assert.equal(clone._id, 10);
            assert.equal(clone.children[0]._id, 11);
            assert.equal(clone.children[1]._id, 12);
            assert.equal(clone.children[1].children[0]._id, 13);
        });

        it("returns the next unused id", function () {
            const source = group("all", [component(), component()]);
            const { nextId } = cloneWithNewIds(source, 5);
            assert.equal(nextId, 8);
        });

        it("returns nextId + 1 for a lone component", function () {
            const { node: clone, nextId } = cloneWithNewIds(component(), 42);
            assert.equal(clone._id, 42);
            assert.equal(nextId, 43);
        });

        it("does not mutate the source ids", function () {
            const source = group("all", [component()]);
            source._id = 99;
            source.children[0]._id = 100;
            cloneWithNewIds(source, 1);
            assert.equal(source._id, 99);
            assert.equal(source.children[0]._id, 100);
        });
    });

    describe("normalizeRoot", function () {
        it("passes an all/any/none group through unchanged", function () {
            const g = group("any", [component()]);
            assert.strictEqual(normalizeRoot(g), g);
        });

        it("wraps a bare component in an all group", function () {
            const c = component({ field: "name" });
            const result = normalizeRoot(c);
            assert.equal(result.type, "all");
            assert.deepEqual(result.children, [c]);
        });

        it("returns an empty all group for null", function () {
            assert.deepEqual(normalizeRoot(null), {
                type: "all",
                children: [],
            });
        });

        it("keeps children of a legacy/unknown-type root", function () {
            const children = [component()];
            const result = normalizeRoot({ type: "legacy", children });
            assert.equal(result.type, "all");
            assert.deepEqual(result.children, children);
        });
    });
});
