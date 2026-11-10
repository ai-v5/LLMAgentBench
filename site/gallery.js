(function () {
  "use strict";
  const tabs = document.querySelector("[data-gallery-tabs]");
  const frame = document.querySelector("[data-gallery-frame]");
  if (!tabs || !frame) return;
  const status = document.querySelector("[data-gallery-status]");
  fetch("site/gallery.json", { cache: "no-cache" })
    .then((response) => {
      if (!response.ok) throw new Error("gallery unavailable");
      return response.json();
    })
    .then((data) => {
      if (!data || data.schema_version !== 1 || !Array.isArray(data.entries) || !data.entries.length) {
        throw new Error("empty gallery");
      }
      const buttons = data.entries.map((entry, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "gallery-tab";
        button.setAttribute("role", "tab");
        button.setAttribute("aria-selected", index === 0 ? "true" : "false");
        button.textContent = entry.label + (entry.effort ? " · " + entry.effort : "");
        button.addEventListener("click", () => select(index));
        tabs.appendChild(button);
        return button;
      });
      function select(index) {
        const entry = data.entries[index];
        buttons.forEach((button, position) => {
          button.setAttribute("aria-selected", position === index ? "true" : "false");
        });
        frame.title = entry.label + " 生成的鳄鱼骑自行车 SVG 动画";
        frame.src = entry.file;
        if (status) status.textContent = entry.note || "";
      }
      select(0);
    })
    .catch(() => {
      const section = document.getElementById("drawing");
      if (section) section.hidden = true;
    });
})();
