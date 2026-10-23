// Slide 8: switch between the Python and R app recordings (and their code), then replay the selected clip.
(function () {
  document.querySelectorAll(".agent-apps").forEach((root) => {
    root.querySelectorAll(".tab").forEach((tab) =>
      tab.addEventListener("click", () => {
        const app = tab.dataset.app;
        root.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t === tab));
        root.querySelectorAll("[data-app]").forEach((el) => {
          if (!el.classList.contains("tab")) el.classList.toggle("hidden", el.dataset.app !== app);
        });
        const demo = root.querySelector(`.app-pane[data-app="${app}"] .demo`);
        if (demo) demo.click();
      }));
  });
})();
