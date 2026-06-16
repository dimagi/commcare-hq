import "commcarehq";
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
            return this.capability.case_types[this.targetCasetype] || {};
        },

        getFieldDef(fieldName) {
            return this.currentFields[fieldName] || null;
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

        // The stored spec and builder state share the same shape, so the only
        // adjustment needed is at the root: the builder always renders a
        // group, so wrap a bare-component or empty/legacy root in an `all`
        // group.
        normalizeRoot(node) {
            if (node && ["all", "any", "none"].includes(node.type)) {
                return node;
            }
            if (node && node.type === "component") {
                return { type: "all", children: [node] };
            }
            return { type: "all", children: (node && node.children) || [] };
        },

        init() {
            this.query = this.normalizeRoot(this.query);
            this.initializeIds(this.query);
        },

        onCasetypeChange() {
            this.query = { type: "all", children: [] };
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

        // Builder state and the stored spec share the same shape, so emitting
        // the spec is just dropping the Alpine-only `_id` keys.
        strippedQuery() {
            return this.stripIds(this.query);
        },
    };
});

Alpine.start();
