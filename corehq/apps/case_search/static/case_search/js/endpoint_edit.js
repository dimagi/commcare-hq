import "commcarehq";
import Alpine from "alpinejs";

document.addEventListener("alpine:init", () => {
  Alpine.data("endpointEditor", () => ({
    mode: "",
    endpointName: "",
    targetType: "project_db",
    targetName: "",
    validationErrors: [],
    capability: {},
    parameters: [],
    filterTree: {type: "and", children: []},

    init() {
      this.mode = JSON.parse(
        document.getElementById("endpoint-mode-data").textContent,
      );
      this.capability = JSON.parse(
        document.getElementById("capability-data").textContent,
      );
      this.parameters = JSON.parse(
        document.getElementById("parameters-data").textContent,
      );
      const parsedTree = JSON.parse(
        document.getElementById("query-data").textContent,
      );
      this.filterTree.type = parsedTree.type || "and";
      this.filterTree.children = parsedTree.children || [];
      this.targetName = JSON.parse(
        document.getElementById("target-name-data").textContent,
      );
      if (
        this.mode === "create" &&
        !this.targetName &&
        this.capability.case_types.length > 0
      ) {
        this.targetName = this.capability.case_types[0].name;
      }
    },

    save() {
      const payload = {
        parameters: this.parameters,
        query: this.filterTree,
      };
      if (this.mode === "create") {
        payload.name = this.endpointName;
        payload.target_type = this.targetType;
        payload.target_name = this.targetName;
      }
      fetch(window.location.pathname, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken":
            document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
            document.cookie.match(/csrftoken=([^;]+)/)?.[1],
        },
        body: JSON.stringify(payload),
      })
        .then((r) => r.json().then((data) => ({ status: r.status, data })))
        .then(({ status, data }) => {
          if (status === 400 && data.errors) {
            this.validationErrors = data.errors;
          } else if (data.redirect) {
            window.location.href = data.redirect;
          }
        });
    },
  }));
});

Alpine.start();
