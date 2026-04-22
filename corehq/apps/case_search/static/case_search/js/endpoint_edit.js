import "commcarehq";
import Alpine from "alpinejs";
import initialPageData from "hqwebapp/js/initial_page_data";

Alpine.data("endpointForm", () => {
    const mode = initialPageData.get("endpoint_mode");
    const postUrl = initialPageData.get("post_url");

    return {
        name: initialPageData.get("initial_name"),
        targetCasetype: initialPageData.get("initial_target_name"),
        parameters: initialPageData.get("initial_parameters"),
        query: initialPageData.get("initial_query"),
        capability: initialPageData.get("capability"),
        errors: [],
        submitting: false,
        mode: mode,
        _nextId: 1,

        get currentFields() {
            if (!this.targetCasetype) {return [];}
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

        getAutoValuesForFieldType(fieldType) {
            return this.capability.auto_values[fieldType] || [];
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
            if (node.child) {
                this.initializeIds(node.child);
            }
        },

        init() {
            this.initializeIds(this.query);
        },

        onCasetypeChange() {
            this.query = { type: "and", children: [] };
        },

        addParameter() {
            this.parameters.push({ name: "", type: "text", required: false });
        },

        removeParameter(idx) {
            this.parameters.splice(idx, 1);
        },

        addCondition(group) {
            if (!group.children) {group.children = [];}
            group.children.push({
                _id: this._nextId++,
                type: "component",
                field: "",
                component: "",
                inputs: {},
            });
        },

        addGroup(parentGroup, type) {
            if (!parentGroup.children) {parentGroup.children = [];}
            parentGroup.children.push({
                _id: this._nextId++,
                type: type,
                children: [],
            });
        },

        addNotGroup(parentGroup) {
            if (!parentGroup.children) {parentGroup.children = [];}
            parentGroup.children.push({
                _id: this._nextId++,
                type: "not",
                child: { _id: this._nextId++, type: "and", children: [] },
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
            if (schema.every((slot) => slot.name in (node.inputs || {}))) {return;}
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
            } else if (valueType === "parameter") {
                node.inputs[slotName] = {
                    type: "parameter",
                    ref: current.ref || "",
                };
            } else if (valueType === "auto_value") {
                node.inputs[slotName] = {
                    type: "auto_value",
                    ref: current.ref || "",
                };
            }
        },

        async submitForm() {
            this.errors = [];

            if (!this.name.trim()) {
                this.errors.push(gettext("Name is required."));
            }
            if (!this.targetCasetype) {
                this.errors.push(gettext("Case type is required."));
            }
            if (this.errors.length > 0) {return;}

            this.submitting = true;
            try {
                const payload = {
                    name: this.name.trim(),
                    target_type: "project_db",
                    target_name: this.targetCasetype,
                    parameters: this.parameters.filter((p) => p.name.trim()),
                    query: this.query,
                };

                const resp = await fetch(postUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": this._getCsrfToken(),
                    },
                    body: JSON.stringify(payload),
                });

                const data = await resp.json();
                if (resp.ok && data.redirect) {
                    window.location.href = data.redirect;
                } else {
                    this.errors = data.errors || [gettext("An unexpected error occurred.")];
                }
            } catch {
                this.errors = [gettext("Network error. Please try again.")];
            } finally {
                this.submitting = false;
            }
        },

        _getCsrfToken() {
            return document.getElementById('csrfTokenContainer').value;
        },
    };
});

Alpine.start();
