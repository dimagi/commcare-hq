// Pure tree operations for the endpoint query builder. Kept free of Alpine and
// page-data dependencies so they can be unit-tested directly.

export function subtreeGroupHeight(node) {
    if (node.type === "component") {
        return 0;
    }
    const heights = (node.children || []).map(subtreeGroupHeight);
    return 1 + Math.max(0, ...heights);
}

export function cloneWithNewIds(node, nextId) {
    const clone = JSON.parse(JSON.stringify(node));
    const assign = (n) => {
        n._id = nextId++;
        (n.children || []).forEach(assign);
    };
    assign(clone);
    return { node: clone, nextId };
}

// The stored spec and builder state share the same shape, so the only
// adjustment needed is at the root: the builder always renders a group, so
// wrap a bare-component or empty/legacy root in an `all` group.
export function normalizeRoot(node) {
    if (node && ["all", "any", "none"].includes(node.type)) {
        return node;
    }
    if (node && node.type === "component") {
        return { type: "all", children: [node] };
    }
    return { type: "all", children: (node && node.children) || [] };
}

// Remove `node` from `parent.children` by identity, returning true if found.
// Identity rather than index because the builder's x-for is keyed by `_id` and
// Alpine does not re-run a child's scope after the list mutates, so a captured
// index goes stale and would delete the wrong sibling.
export function removeChild(parent, node) {
    const idx = (parent.children || []).indexOf(node);
    if (idx === -1) {
        return false;
    }
    parent.children.splice(idx, 1);
    return true;
}
