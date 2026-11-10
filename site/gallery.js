(function () {
  "use strict";
  const tabs = document.querySelector("[data-gallery-tabs]");
  const canvas = document.querySelector("[data-gallery-canvas]");
  if (!tabs || !canvas) return;
  const status = document.querySelector("[data-gallery-status]");
  const htmlLink = document.querySelector("[data-gallery-html]");
  let requestId = 0;
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
        const current = ++requestId;
        canvas.setAttribute("aria-label", entry.label + " " + entry.effort + " 生成的鳄鱼骑自行车动画");
        if (status) status.textContent = entry.note || "";
        if (htmlLink) {
          htmlLink.hidden = !entry.html;
          if (entry.html) htmlLink.setAttribute("href", entry.html);
        }
        if (entry.html) {
          const frame = document.createElement("iframe");
          frame.setAttribute("sandbox", "");
          frame.setAttribute("referrerpolicy", "no-referrer");
          frame.setAttribute("title", entry.label + " " + entry.effort + " 的鳄鱼动画");
          frame.src = entry.html;
          canvas.replaceChildren(frame);
          return;
        }
        fetch(entry.svg, { cache: "no-cache" })
          .then((response) => {
            if (!response.ok) throw new Error("svg unavailable");
            return response.text();
          })
          .then((svg) => {
            if (current !== requestId) return;
            canvas.innerHTML = svg
              .replace(/<script[\s\S]*?<\/script>/gi, "")
              .replace(/<foreignObject[\s\S]*?<\/foreignObject>/gi, "");
          })
          .catch(() => {
            if (current === requestId) canvas.textContent = "该输出暂时无法加载";
          });
      }
      select(0);
    })
    .catch(() => {
      const section = document.getElementById("drawing");
      if (section) section.hidden = true;
    });
})();
