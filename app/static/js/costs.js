document.addEventListener("DOMContentLoaded", async () => {
    const totalCostCtx = document.getElementById("totalCostChart")?.getContext("2d");
    const totalTokenCostValue = document.getElementById("totalTokenCostValue");
    const dailyCtx = document.getElementById("dailyChart")?.getContext("2d");
    const monthlyCtx = document.getElementById("monthlyChart")?.getContext("2d");

    if (!totalCostCtx && !dailyCtx && !monthlyCtx) return;

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

    function formatUsd(value) {
        return `$${Number(value ?? 0).toFixed(6)}`;
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
        const tokensByLabelAndModel = new Map(
            rows.map((row) => [`${row[labelKey]}::${row.model}`, row.total_tokens ?? 0]),
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
            tokensByLabelAndModel,
        };
    }

    // Total cost circular chart
    try {
        if (totalCostCtx) {
            const monthlyResp = await fetch("/api/costs/monthly");
            const monthlyData = await monthlyResp.json();
            const totalsByModel = new Map();
            const callsByModel = new Map();
            const tokensByModel = new Map();
            for (const row of monthlyData) {
                totalsByModel.set(
                    row.model,
                    (totalsByModel.get(row.model) ?? 0) + Number(row.total ?? 0),
                );
                callsByModel.set(
                    row.model,
                    (callsByModel.get(row.model) ?? 0) + Number(row.calls ?? 0),
                );
                tokensByModel.set(
                    row.model,
                    (tokensByModel.get(row.model) ?? 0) + Number(row.total_tokens ?? 0),
                );
            }
            const labels = [...totalsByModel.keys()];
            const values = [...totalsByModel.values()];
            const calls = labels.map((model) => callsByModel.get(model) ?? 0);
            const tokens = labels.map((model) => tokensByModel.get(model) ?? 0);
            const totalCost = values.reduce((sum, value) => sum + value, 0);
            if (totalTokenCostValue) totalTokenCostValue.textContent = formatUsd(totalCost);
            const hasData = values.length > 0;

            new Chart(totalCostCtx, {
                type: "doughnut",
                data: {
                    labels: hasData ? labels : ["No data"],
                    datasets: [{
                        data: hasData ? values : [1],
                        backgroundColor: hasData
                            ? labels.map((_, index) => modelColors[index % modelColors.length] + "99")
                            : ["#e5e7eb"],
                        borderColor: hasData
                            ? labels.map((_, index) => modelColors[index % modelColors.length])
                            : ["#d1d5db"],
                        borderWidth: 1,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    aspectRatio: 4,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (context) => {
                                    if (!hasData) return "No model cost data";
                                    const index = context.dataIndex;
                                    return `${context.label}: ${formatUsd(context.parsed)} (${calls[index]} calls, ${tokens[index]} tokens)`;
                                },
                            },
                        },
                    },
                },
            });
        }
    } catch (e) {
        console.error("Failed to load total cost:", e);
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
                                const tokens = dailyChartData.tokensByLabelAndModel.get(
                                    `${context.label}::${model}`,
                                ) ?? 0;
                                return `${model}: $${context.parsed.y.toFixed(6)} (${calls} calls, ${tokens} tokens)`;
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
                                const tokens = monthlyChartData.tokensByLabelAndModel.get(
                                    `${context.label}::${model}`,
                                ) ?? 0;
                                return `${model}: $${context.parsed.y.toFixed(6)} (${calls} calls, ${tokens} tokens)`;
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
