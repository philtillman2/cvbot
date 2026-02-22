/**
 * Split the final markdown into sections and render strengths/weaknesses
 * as side-by-side cards, keeping the rest as normal markdown.
 */
function layoutResults(md) {
    // Split on h2 headers, keeping the header text
    const parts = md.split(/^## /m);
    const intro = parts[0]; // text before first h2

    const sections = {};
    for (let i = 1; i < parts.length; i++) {
        const newline = parts[i].indexOf('\n');
        const title = (newline === -1 ? parts[i] : parts[i].slice(0, newline)).trim();
        const body = newline === -1 ? '' : parts[i].slice(newline + 1);
        sections[title] = body;
    }

    let html = marked.parse(intro);

    // Find the strengths and weaknesses sections (flexible matching)
    const strengthKey = Object.keys(sections).find(k => /strength|pros/i.test(k));
    const weaknessKey = Object.keys(sections).find(k => /weakness|cons/i.test(k));

    if (strengthKey && weaknessKey) {
        html += '<div class="fit-cards-row">';
        html += `<div class="fit-card fit-card-strengths">
            <div class="fit-card-header"><i class="bi bi-hand-thumbs-up-fill me-2"></i>${strengthKey}</div>
            <div class="fit-card-body">${marked.parse(sections[strengthKey])}</div>
        </div>`;
        html += `<div class="fit-card fit-card-weaknesses">
            <div class="fit-card-header"><i class="bi bi-hand-thumbs-down-fill me-2"></i>${weaknessKey}</div>
            <div class="fit-card-body">${marked.parse(sections[weaknessKey])}</div>
        </div>`;
        html += '</div>';
    }

    // Render remaining sections (Overall Assessment, Verdict, etc.)
    for (const [title, body] of Object.entries(sections)) {
        if (title === strengthKey || title === weaknessKey) continue;
        html += marked.parse(`## ${title}\n${body}`);
    }

    return html;
}

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('jobFitForm');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const modelSelect = document.getElementById('modelSelect');
    const resultsSection = document.getElementById('resultsSection');
    const resultsContent = document.getElementById('resultsContent');
    const usageSummary = document.getElementById('jobFitUsageSummary');
    const usageTokenText = document.getElementById('jobFitUsageTokenText');
    const usageProgressBar = document.getElementById('jobFitUsageProgressBar');
    const usageCurrentCost = document.getElementById('jobFitUsageCurrentCost');
    const usageMaxCost = document.getElementById('jobFitUsageMaxCost');
    const modelStorageKey = 'cvbot.selectedModel';

    function updateUsageSummary(usage) {
        const dailyLimit = usage.daily_limit_usd || 0;
        const dailyTotal = usage.daily_total_usd || 0;
        const pct = dailyLimit > 0 ? Math.min((dailyTotal / dailyLimit) * 100, 100) : 0;
        usageSummary?.classList.remove('d-none');
        if (usageTokenText) {
            usageTokenText.textContent =
                `${usage.input_tokens} in / ${usage.output_tokens} out tokens`;
        }
        if (usageCurrentCost) usageCurrentCost.textContent = `$${dailyTotal.toFixed(2)}`;
        if (usageMaxCost) usageMaxCost.textContent = `$${dailyLimit.toFixed(2)}`;
        if (usageProgressBar) {
            usageProgressBar.style.width = `${pct}%`;
            usageProgressBar.setAttribute('aria-valuenow', String(pct));
        }
    }

    async function initializeUsageSummary() {
        try {
            const resp = await fetch('/api/costs/today');
            if (!resp.ok) return;
            const usage = await resp.json();
            updateUsageSummary({ ...usage, input_tokens: 0, output_tokens: 0 });
        } catch (_) {}
    }

    initializeUsageSummary();

    const savedModel = localStorage.getItem(modelStorageKey);
    if (savedModel && [...modelSelect.options].some((option) => option.value === savedModel)) {
        modelSelect.value = savedModel;
    }
    modelSelect.addEventListener('change', () => {
        localStorage.setItem(modelStorageKey, modelSelect.value);
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const candidateId = document.getElementById('candidateSelect').value;
        const model = modelSelect.value;
        const jobDescription = document.getElementById('jobDescription').value.trim();

        if (!jobDescription) return;

        // Show results section, clear previous
        resultsSection.classList.remove('d-none');
        resultsContent.innerHTML = '<span class="streaming-cursor"></span>';
        analyzeBtn.disabled = true;
        analyzeBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Analyzing...';

        let fullText = '';

        try {
            const resp = await fetch('/api/job-fit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    candidate_id: candidateId,
                    model: model,
                    job_description: jobDescription,
                }),
            });

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const text = decoder.decode(value, { stream: true });
                const lines = text.split('\n');

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const data = line.slice(6).trim();
                    if (data === '[DONE]') continue;

                    try {
                        const chunk = JSON.parse(data);
                        if (chunk.type === 'token') {
                            fullText += chunk.content;
                            resultsContent.innerHTML = marked.parse(fullText) +
                                '<span class="streaming-cursor"></span>';
                        } else if (chunk.type === 'usage') {
                            updateUsageSummary(chunk);
                        }
                    } catch (_) {}
                }
            }
        } catch (err) {
            fullText += '\n\n**Error:** ' + err.message;
        }

        // Final render: lay out strengths/weaknesses side-by-side
        resultsContent.innerHTML = layoutResults(fullText);
        analyzeBtn.disabled = false;
        analyzeBtn.innerHTML = '<i class="bi bi-search me-1"></i> Analyze Fit';

        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    });
});
