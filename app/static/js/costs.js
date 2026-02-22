document.addEventListener("DOMContentLoaded", async () => {
    const dailyCtx = document.getElementById("dailyChart")?.getContext("2d");
    const monthlyCtx = document.getElementById("monthlyChart")?.getContext("2d");

    if (!dailyCtx || !monthlyCtx) return;

    const modelColors = [
        "#a855f7",
        "#3b82f6",
        "#10b981",
        "#f59e0b",
        "#ef4444",
        "#8b5cf6",
        "#06b6d4",
        "#84cc16",
    ];

    function formatPrice(price) {
        if (price == null) return "n/a";
        return Number(price).toFixed(2);
    }

    function formatLegendLabel(model, pricing) {
        if (!pricing || pricing.input == null || pricing.output == null) return `${model} ($n/a per 1M)`;
        return `${model} ($${formatPrice(pricing.input)}/$${formatPrice(pricing.output)} per 1M in/out)`;
    }

    function buildStackedDatasets(rows, labelKey) {
        const labels = [...new Set(rows.map((row) => row[labelKey]))];
        const models = [...new Set(rows.map((row) => row.model))];
        const totalsByLabelAndModel = new Map(
            rows.map((row) => [`${row[labelKey]}::${row.model}`, row.total]),
        );
        const callsByLabelAndModel = new Map(
            rows.map((row) => [`${row[labelKey]}::${row.model}`, row.calls]),
        );
        const pricingByModel = new Map(
            rows.map((row) => [
                row.model,
                {
                    input: row.input_cost_per_1m,
                    output: row.output_cost_per_1m,
                },
            ]),
        );

        return {
            labels,
            datasets: models.map((model, index) => ({
                label: formatLegendLabel(model, pricingByModel.get(model)),
                modelId: model,
                data: labels.map((label) => totalsByLabelAndModel.get(`${label}::${model}`) ?? 0),
                backgroundColor: modelColors[index % modelColors.length] + "99",
                borderColor: modelColors[index % modelColors.length],
                borderWidth: 1,
            })),
            callsByLabelAndModel,
        };
    }

    // Daily cumulative bar chart
    try {
        const dailyResp = await fetch("/api/costs/daily");
        const dailyData = await dailyResp.json();

        const dailyChartData = buildStackedDatasets(dailyData, "date");
        new Chart(dailyCtx, {
            type: "bar",
            data: {
                labels: dailyChartData.labels,
                datasets: dailyChartData.datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const model = context.dataset.modelId ?? context.dataset.label;
                                const calls = dailyChartData.callsByLabelAndModel.get(
                                    `${context.label}::${model}`,
                                ) ?? 0;
                                return `${model}: $${context.parsed.y.toFixed(6)} (${calls} calls)`;
                            },
                        },
                    },
                },
                scales: {
                    y: { beginAtZero: true, stacked: true, title: { display: true, text: "USD" } },
                    x: { stacked: true, title: { display: true, text: "Date" } },
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

        const monthlyChartData = buildStackedDatasets(monthlyData, "month");
        new Chart(monthlyCtx, {
            type: "bar",
            data: {
                labels: monthlyChartData.labels,
                datasets: monthlyChartData.datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const model = context.dataset.modelId ?? context.dataset.label;
                                const calls = monthlyChartData.callsByLabelAndModel.get(
                                    `${context.label}::${model}`,
                                ) ?? 0;
                                return `${model}: $${context.parsed.y.toFixed(6)} (${calls} calls)`;
                            },
                        },
                    },
                },
                scales: {
                    y: { beginAtZero: true, stacked: true, title: { display: true, text: "USD" } },
                    x: { stacked: true, title: { display: true, text: "Month" } },
                },
            },
        });
    } catch (e) {
        console.error("Failed to load monthly costs:", e);
    }
});
