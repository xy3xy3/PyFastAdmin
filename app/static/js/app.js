// 全局交互脚本（HTMX + Alpine 事件桥接）
(() => {
  const toastEl = document.getElementById("toast");
  const titleEl = toastEl?.querySelector("[data-toast-title]");
  const messageEl = toastEl?.querySelector("[data-toast-message]");

  let toastTimer = null;

  const showToast = (detail = {}) => {
    if (!toastEl) return;
    const { title = "操作完成", message = "已成功提交变更", variant = "success" } = detail;

    toastEl.dataset.variant = variant;
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

  document.body.addEventListener("htmx:responseError", () => {
    showToast({
      title: "请求失败",
      message: "服务器暂时不可用，请稍后再试。",
      variant: "error",
    });
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-perm-action]");
    if (!button) return;
    const scope = button.closest("[data-perm-scope]") || document;
    const checkboxes = scope.querySelectorAll(
      'input[type="checkbox"][name^="perm_"]'
    );
    if (!checkboxes.length) return;
    const action = button.dataset.permAction;
    if (action === "all") {
      checkboxes.forEach((item) => (item.checked = true));
      return;
    }
    if (action === "none") {
      checkboxes.forEach((item) => (item.checked = false));
      return;
    }
    if (action === "invert") {
      checkboxes.forEach((item) => (item.checked = !item.checked));
    }
  });
})();
