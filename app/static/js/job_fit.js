function parseMarkdownSafe(markdown) {
    if (typeof marked === 'undefined') return markdown;
    const html = marked.parse(markdown);
    return typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(html) : html;
}

function extractSections(md) {
    const parts = md.split(/^## /m);
    const intro = parts[0];
    const sections = [];

    for (let i = 1; i < parts.length; i++) {
        const newline = parts[i].indexOf('\n');
        const title = (newline === -1 ? parts[i] : parts[i].slice(0, newline)).trim();
        const body = newline === -1 ? '' : parts[i].slice(newline + 1);
        sections.push({ title, body });
    }

    return { intro, sections };
}

function ensureResultsLayout(container) {
    if (container.querySelector('[data-job-fit-layout]')) return;
    container.innerHTML = `
        <div data-job-fit-layout>
            <div data-job-fit-intro></div>
            <div class="fit-cards-row mt-3">
                <div class="fit-card fit-card-strengths">
                    <div class="fit-card-header" data-job-fit-strength-title><i class="bi bi-hand-thumbs-up-fill me-2"></i>Strengths & Pros</div>
                    <div class="fit-card-body" data-job-fit-strength-body></div>
                </div>
                <div class="fit-card fit-card-weaknesses">
                    <div class="fit-card-header" data-job-fit-weakness-title><i class="bi bi-hand-thumbs-down-fill me-2"></i>Weaknesses & Cons</div>
                    <div class="fit-card-body" data-job-fit-weakness-body></div>
                </div>
            </div>
            <div class="mt-3" data-job-fit-other></div>
        </div>
    `;
}

function renderStreamingResults(container, md, showCursor = false) {
    ensureResultsLayout(container);
    const { intro, sections } = extractSections(md);
    const strength = sections.find((section) => /strength|pros/i.test(section.title));
    const weakness = sections.find((section) => /weakness|cons/i.test(section.title));
    const otherSections = sections.filter((section) => section !== strength && section !== weakness);

    const introEl = container.querySelector('[data-job-fit-intro]');
    const strengthTitleEl = container.querySelector('[data-job-fit-strength-title]');
    const strengthBodyEl = container.querySelector('[data-job-fit-strength-body]');
    const weaknessTitleEl = container.querySelector('[data-job-fit-weakness-title]');
    const weaknessBodyEl = container.querySelector('[data-job-fit-weakness-body]');
    const otherEl = container.querySelector('[data-job-fit-other]');

    introEl.innerHTML = parseMarkdownSafe(intro);
    strengthTitleEl.innerHTML = `<i class="bi bi-hand-thumbs-up-fill me-2"></i>${strength?.title || 'Strengths & Pros'}`;
    strengthBodyEl.innerHTML = parseMarkdownSafe(strength?.body || '');
    weaknessTitleEl.innerHTML = `<i class="bi bi-hand-thumbs-down-fill me-2"></i>${weakness?.title || 'Weaknesses & Cons'}`;
    weaknessBodyEl.innerHTML = parseMarkdownSafe(weakness?.body || '');
    otherEl.innerHTML = otherSections.map((section) => parseMarkdownSafe(`## ${section.title}\n${section.body}`)).join('');

    for (const el of container.querySelectorAll('.streaming-cursor')) {
        el.remove();
    }
    if (!showCursor) return;

    let cursorTarget = introEl;
    if (sections.length > 0) {
        const lastSection = sections[sections.length - 1];
        if (lastSection === strength) {
            cursorTarget = strengthBodyEl;
        } else if (lastSection === weakness) {
            cursorTarget = weaknessBodyEl;
        } else {
            cursorTarget = otherEl;
        }
    }
    cursorTarget.insertAdjacentHTML('beforeend', '<span class="streaming-cursor"></span>');
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
    const usageProgressValue = document.getElementById('jobFitUsageCurrentCost');
    const modelStorageKey = 'cvbot.selectedModel';

    function updateUsageSummary(usage) {
        const dailyLimit = usage.daily_limit_usd || 0;
        const dailyTotal = usage.daily_total_usd || 0;
        const shownInputTokens = usage.daily_input_tokens ?? usage.input_tokens ?? 0;
        const shownOutputTokens = usage.daily_output_tokens ?? usage.output_tokens ?? 0;
        const rawPct = dailyLimit > 0 ? (dailyTotal / dailyLimit) * 100 : 0;
        const pct = Math.min(Math.max(rawPct, dailyTotal > 0 ? 1 : 0), 100);
        usageSummary?.classList.remove('d-none');
        if (usageTokenText) {
            usageTokenText.textContent = `${shownInputTokens} in / ${shownOutputTokens} out tokens`;
        }
        const formattedDailyCost =
            dailyTotal > 0 && dailyTotal < 0.01 ? `$${dailyTotal.toFixed(5)}` : `$${dailyTotal.toFixed(2)}`;
        if (usageCurrentCost) usageCurrentCost.textContent = formattedDailyCost;
        if (usageProgressValue) usageProgressValue.textContent = formattedDailyCost;
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
            updateUsageSummary(usage);
        } catch (e) {
            console.error(e);
        }
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
        resultsContent.innerHTML = '';
        renderStreamingResults(resultsContent, '', true);
        analyzeBtn.disabled = true;
        analyzeBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>';

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
                            renderStreamingResults(resultsContent, fullText, true);
                        } else if (chunk.type === 'usage') {
                            updateUsageSummary(chunk);
                        }
                    } catch (e) {
                        console.error(e);
                    }
                }
            }
        } catch (err) {
            fullText += '\n\n**Error:** ' + err.message;
            console.error(err);
        }

        renderStreamingResults(resultsContent, fullText, false);
        analyzeBtn.disabled = false;
        analyzeBtn.innerHTML = '<i class="bi bi-search me-1"></i>';

        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    });
});
