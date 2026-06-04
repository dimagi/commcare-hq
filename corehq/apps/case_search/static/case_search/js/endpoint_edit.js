import "commcarehq";
import "hqwebapp/js/htmx_base";
import Alpine from "alpinejs";
import initialPageData from "hqwebapp/js/initial_page_data";

Alpine.data("endpointForm", () => {
    const mode = initialPageData.get("endpoint_mode");

    return {
        name: initialPageData.get("initial_name"),
        targetType: initialPageData.get("initial_target_type"),
        targetCasetype: initialPageData.get("initial_target_name"),
        query: initialPageData.get("initial_query"),
        capability: initialPageData.get("capability"),
        mode: mode,
        _nextId: 1,

        get currentFields() {
            if (!this.targetCasetype) {
                return [];
            }
            const ct = this.capability.case_types.find(
                (c) => c.name === this.targetCasetype,
            );
            return ct ? ct.fields : [];
        },

        getFieldDef(fieldName) {
            return this.currentFields.find((f) => f.name === fieldName) || null;
        },

        getOperationsForField(fieldName) {
            const f = this.getFieldDef(fieldName);
            return f ? f.operations : [];
        },

        getInputSchemaForOperation(operation) {
            return this.capability.component_input_schemas[operation] || [];
        },

        getFieldType(fieldName) {
            const f = this.getFieldDef(fieldName);
            return f ? f.type : "";
        },

        typeIconClass(type) {
            return (
                {
                    text: "fa-solid fa-font",
                    number: "fa-solid fa-hashtag",
                    date: "fa-solid fa-calendar-days",
                    datetime: "fa-solid fa-calendar-days",
                    select: "fa-solid fa-list",
                    geopoint: "fa-solid fa-location-dot",
                }[type] || "fa-solid fa-circle"
            );
        },

        initializeIds(node) {
            node._id = this._nextId++;
            if (node.children) {
                node.children.forEach((child) => this.initializeIds(child));
            }
        },

        // Convert a stored spec node into builder state: `not` wrappers
        // become a `negated` flag on the group they wrap, and anything that
        // isn't a group (legacy `{}` roots, bare components) is wrapped in
        // an AND group.
        normalizeNode(node) {
            if (!node || !node.type) {
                return {
                    type: "and",
                    negated: false,
                    children: (node && node.children) || [],
                };
            }
            if (node.type === "not") {
                const inner = this.normalizeNode(node.child);
                inner.negated = !inner.negated;
                return inner;
            }
            if (node.type === "and" || node.type === "or") {
                return {
                    type: node.type,
                    negated: !!node.negated,
                    children: (node.children || []).map((child) =>
                        child && child.type === "component"
                            ? child
                            : this.normalizeNode(child),
                    ),
                };
            }
            // bare component at the root
            return { type: "and", negated: false, children: [node] };
        },

        init() {
            this.query = this.normalizeNode(this.query);
            this.initializeIds(this.query);
        },

        onCasetypeChange() {
            this.query = { type: "and", negated: false, children: [] };
        },

        _newCondition() {
            return {
                _id: this._nextId++,
                type: "component",
                field: "",
                component: "",
                inputs: {},
            };
        },

        addCondition(group) {
            if (!group.children) {
                group.children = [];
            }
            group.children.push(this._newCondition());
        },

        addGroup(parentGroup, type) {
            if (!parentGroup.children) {
                parentGroup.children = [];
            }
            parentGroup.children.push({
                _id: this._nextId++,
                type: type,
                negated: false,
                children: [this._newCondition()],
            });
        },

        removeNode(parentGroup, idx) {
            parentGroup.children.splice(idx, 1);
        },

        onFieldChange(node) {
            node.component = "";
            node.inputs = {};
        },

        onComponentChange(node) {
            const schema = this.getInputSchemaForOperation(node.component);
            if (schema.every((slot) => slot.name in (node.inputs || {}))) {
                return;
            }
            node.inputs = {};
            for (const slot of schema) {
                node.inputs[slot.name] = { type: "constant", value: "" };
            }
        },

        getInputValue(node, slotName) {
            if (!node.inputs[slotName]) {
                node.inputs[slotName] = { type: "constant", value: "" };
            }
            return node.inputs[slotName];
        },

        setInputType(node, slotName, valueType) {
            const current = node.inputs[slotName] || {};
            if (valueType === "constant") {
                node.inputs[slotName] = {
                    type: "constant",
                    value: current.value || "",
                };
            }
        },

        // Strip Alpine-only `_id` keys so the persisted query JSON stays clean.
        stripIds(node) {
            if (Array.isArray(node)) {
                return node.map((n) => this.stripIds(n));
            }
            if (node && typeof node === "object") {
                const out = {};
                for (const [key, value] of Object.entries(node)) {
                    if (key === "_id") {
                        continue;
                    }
                    out[key] = this.stripIds(value);
                }
                return out;
            }
            return node;
        },

        // Convert builder state back into the stored spec format: drop the
        // Alpine-only keys (`_id`, `negated`) and wrap negated groups in a
        // `not` node.
        toSpecNode(node) {
            if (node.type === "and" || node.type === "or") {
                const group = {
                    type: node.type,
                    children: (node.children || []).map((child) =>
                        this.toSpecNode(child),
                    ),
                };
                return node.negated ? { type: "not", child: group } : group;
            }
            return this.stripIds(node);
        },

        strippedQuery() {
            return this.toSpecNode(this.query);
        },
    };
});

Alpine.start();
