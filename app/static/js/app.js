// 全局交互脚本（HTMX + Alpine 事件桥接）
(() => {
  const toastEl = document.getElementById("toast");
  const titleEl = toastEl?.querySelector("[data-toast-title]");
  const messageEl = toastEl?.querySelector("[data-toast-message]");

  let toastTimer = null;

  const normalizeVariant = (variant) => {
    if (!variant) return "success";
    const value = String(variant).toLowerCase();
    if (["warn", "warning"].includes(value)) return "warning";
    if (["error", "danger", "fail", "failure"].includes(value)) return "error";
    if (["success", "ok", "done"].includes(value)) return "success";
    return "success";
  };

  const showToast = (detail = {}) => {
    if (!toastEl) return;
    const { title = "操作完成", message = "已成功提交变更", variant = "success" } = detail;

    toastEl.dataset.variant = normalizeVariant(variant);
    if (titleEl) titleEl.textContent = title;
    if (messageEl) messageEl.textContent = message;

    toastEl.classList.remove("opacity-0", "pointer-events-none");
    toastEl.classList.add("opacity-100");

    if (toastTimer) window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      toastEl.classList.add("opacity-0", "pointer-events-none");
      toastEl.classList.remove("opacity-100");
    }, 2600);
  };

  document.body.addEventListener("rbac-toast", (event) => {
    showToast(event.detail || {});
  });

  document.body.addEventListener("admin-toast", (event) => {
    showToast(event.detail || {});
  });

  document.body.addEventListener("htmx:responseError", (event) => {
    const xhr = event.detail?.xhr;
    if (xhr?.status === 403) {
      showToast({
        title: "无权限",
        message: xhr.responseText || "当前账号没有执行该操作的权限。",
        variant: "error",
      });
      return;
    }

    showToast({
      title: "请求失败",
      message: "服务器暂时不可用，请稍后再试。",
      variant: "error",
    });
  });

  const actionSelector = 'input[type="checkbox"][name^="perm_"]';
  const readAction = "read";

  const getActionCheckboxes = (scope) =>
    Array.from(scope.querySelectorAll(actionSelector));

  const getActionName = (checkbox) =>
    checkbox.getAttribute("data-perm-action-value") || checkbox.value || "";

  const syncReadDependency = (scope) => {
    const root = scope || document;
    root.querySelectorAll("[data-perm-row]").forEach((row) => {
      const actionBoxes = getActionCheckboxes(row);
      const readCheckbox = actionBoxes.find(
        (item) => getActionName(item) === readAction
      );
      if (!readCheckbox) return;

      const mutatingBoxes = actionBoxes.filter(
        (item) => getActionName(item) !== readAction
      );

      if (!readCheckbox.checked) {
        mutatingBoxes.forEach((item) => {
          item.checked = false;
          item.disabled = true;
        });
        return;
      }

      mutatingBoxes.forEach((item) => {
        item.disabled = false;
      });
    });
  };

  const resolveToggleState = (checkboxes) => {
    if (!checkboxes.length) {
      return { checked: false, indeterminate: false };
    }
    const checkedCount = checkboxes.filter((item) => item.checked).length;
    if (checkedCount === 0) {
      return { checked: false, indeterminate: false };
    }
    if (checkedCount === checkboxes.length) {
      return { checked: true, indeterminate: false };
    }
    return { checked: false, indeterminate: true };
  };

  const syncRowToggle = (rowEl) => {
    const toggle = rowEl.querySelector("[data-perm-row-toggle]");
    if (!toggle) return;
    const state = resolveToggleState(getActionCheckboxes(rowEl));
    toggle.checked = state.checked;
    toggle.indeterminate = state.indeterminate;
  };

  const syncGroupToggle = (groupEl) => {
    const toggle = groupEl.querySelector("[data-perm-group-toggle]");
    if (!toggle) return;
    const state = resolveToggleState(getActionCheckboxes(groupEl));
    toggle.checked = state.checked;
    toggle.indeterminate = state.indeterminate;
  };

  const syncPermToggles = (scope) => {
    const root = scope || document;
    root.querySelectorAll("[data-perm-row]").forEach(syncRowToggle);
    root.querySelectorAll("[data-perm-group]").forEach(syncGroupToggle);
  };

  const findScope = (node) =>
    (node instanceof Element && node.closest("[data-perm-scope]")) || document;

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-perm-action]");
    if (!button) return;
    const scope = findScope(button);
    const checkboxes = getActionCheckboxes(scope);
    if (!checkboxes.length) return;
    const action = button.getAttribute("data-perm-action");
    if (action === "all") {
      checkboxes.forEach((item) => (item.checked = true));
      syncReadDependency(scope);
      syncPermToggles(scope);
      return;
    }
    if (action === "none") {
      checkboxes.forEach((item) => (item.checked = false));
      syncReadDependency(scope);
      syncPermToggles(scope);
      return;
    }
    if (action === "invert") {
      checkboxes.forEach((item) => (item.checked = !item.checked));
      syncReadDependency(scope);
      syncPermToggles(scope);
    }
  });

  document.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) return;
    if (target.matches("[data-perm-row-toggle]")) {
      const row = target.closest("[data-perm-row]");
      if (!row) return;
      getActionCheckboxes(row).forEach((item) => {
        item.checked = target.checked;
      });
      const scope = findScope(row);
      syncReadDependency(scope);
      syncPermToggles(scope);
      return;
    }
    if (target.matches("[data-perm-group-toggle]")) {
      const group = target.closest("[data-perm-group]");
      if (!group) return;
      getActionCheckboxes(group).forEach((item) => {
        item.checked = target.checked;
      });
      const scope = findScope(group);
      syncReadDependency(scope);
      syncPermToggles(scope);
      return;
    }
    if (target.matches(actionSelector)) {
      const row = target.closest("[data-perm-row]");
      if (row) {
        const rowActions = getActionCheckboxes(row);
        const readCheckbox = rowActions.find(
          (item) => getActionName(item) === readAction
        );
        if (
          readCheckbox &&
          target !== readCheckbox &&
          target.checked &&
          !readCheckbox.checked
        ) {
          readCheckbox.checked = true;
        }
      }
      const scope = findScope(target);
      syncReadDependency(scope);
      syncPermToggles(scope);
    }
  });

  const syncAfterSwap = (event) => {
    const target = event.target;
    if (target instanceof Element) {
      syncReadDependency(target);
      syncPermToggles(target);
    }
  };

  document.body.addEventListener("htmx:afterSwap", syncAfterSwap);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      syncReadDependency(document);
      syncPermToggles(document);
    });
  } else {
    syncReadDependency(document);
    syncPermToggles(document);
  }
})();
