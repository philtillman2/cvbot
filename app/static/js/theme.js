// Theme: auto-detect system preference, allow manual toggle
(function () {
    const stored = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const theme = stored || (prefersDark ? "dark" : "light");
    document.documentElement.setAttribute("data-bs-theme", theme);
})();

document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("themeToggle");
    const icon = document.getElementById("themeToggleIcon");
    const label = document.getElementById("themeToggleLabel");
    if (!btn) return;

    function updateToggleAppearance(currentTheme) {
        const nextTheme = currentTheme === "dark" ? "light" : "dark";
        if (icon) {
            icon.classList.remove("bi-sun", "bi-moon-stars");
            icon.classList.add(nextTheme === "light" ? "bi-sun" : "bi-moon-stars");
        }
    }

    updateToggleAppearance(document.documentElement.getAttribute("data-bs-theme"));

    btn.addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-bs-theme");
        const next = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-bs-theme", next);
        localStorage.setItem("theme", next);
        updateToggleAppearance(next);
    });
});
