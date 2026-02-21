document.addEventListener("DOMContentLoaded", async () => {
    const dailyCtx = document.getElementById("dailyChart")?.getContext("2d");
    const monthlyCtx = document.getElementById("monthlyChart")?.getContext("2d");

    if (!dailyCtx || !monthlyCtx) return;

    const accentColor = getComputedStyle(document.documentElement)
        .getPropertyValue("--accent")
        .trim() || "#a855f7";

    // Daily cumulative line chart
    try {
        const dailyResp = await fetch("/api/costs/daily");
        const dailyData = await dailyResp.json();

        new Chart(dailyCtx, {
            type: "line",
            data: {
                labels: dailyData.map((d) => d.date),
                datasets: [
                    {
                        label: "Cumulative Cost (USD)",
                        data: dailyData.map((d) => d.cumulative),
                        borderColor: accentColor,
                        backgroundColor: accentColor + "33",
                        fill: true,
                        tension: 0.3,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: "USD" } },
                    x: { title: { display: true, text: "Date" } },
                },
            },
        });
    } catch (e) {
        console.error("Failed to load daily costs:", e);
    }

    // Monthly bar chart
    try {
        const monthlyResp = await fetch("/api/costs/monthly");
        const monthlyData = await monthlyResp.json();

        new Chart(monthlyCtx, {
            type: "bar",
            data: {
                labels: monthlyData.map((d) => d.month),
                datasets: [
                    {
                        label: "Monthly Cost (USD)",
                        data: monthlyData.map((d) => d.total),
                        backgroundColor: accentColor + "99",
                        borderColor: accentColor,
                        borderWidth: 1,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: "USD" } },
                    x: { title: { display: true, text: "Month" } },
                },
            },
        });
    } catch (e) {
        console.error("Failed to load monthly costs:", e);
    }
});
