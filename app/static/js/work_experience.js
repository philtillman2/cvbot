/* work_experience.js – per-item inline editing */
(function () {
    "use strict";

    const MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    let data = window.__profileData;
    const candidateId = window.__candidateId;

    // Per-item editing state
    const editingKeys = new Set();
    const snapshots = {};  // key → deep-copied data, or null for newly-added items

    /* ── helpers ─────────────────────────────────────────── */
    const h = (tag, attrs, ...children) => {
        const el = document.createElement(tag);
        if (attrs) Object.entries(attrs).forEach(([k, v]) => {
            if (k === "className") el.className = v;
            else if (k.startsWith("on")) el.addEventListener(k.slice(2).toLowerCase(), v);
            else el.setAttribute(k, v);
        });
        children.flat(Infinity).forEach(c => {
            if (c == null) return;
            el.append(typeof c === "string" ? document.createTextNode(c) : c);
        });
        return el;
    };

    function formatDate(d) {
        if (!d) return "";
        if (d.present) return "Present";
        const y = d.year, m = d.month;
        if (y && m && m >= 1 && m <= 12) return `${MONTHS[m]} ${y}`;
        if (y) return String(y);
        return "";
    }

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text ?? "";
        return div.innerHTML;
    }

    function parseMarkdownSafe(markdown) {
        const source = markdown ?? "";
        if (typeof marked === "undefined") return escapeHtml(source).replace(/\n/g, "<br>");
        const html = marked.parse(source);
        return typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(html) : html;
    }

    function normalizePublicationFields() {
        if (!Array.isArray(data?.publications)) return;
        data.publications.forEach(pub => {
            if (!pub) return;
            if (!pub.publication_name) pub.publication_name = pub.publication || pub.journal || "";
            delete pub.publication;
            delete pub.journal;
        });
    }

    /* ── edit-mode field helpers ─────────────────────────── */
    function editableField(value, onChange, opts = {}) {
        const isTextarea = opts.multiline;
        const el = document.createElement(isTextarea ? "textarea" : "input");
        el.className = "we-edit-field form-control form-control-sm" + (opts.className ? " " + opts.className : "");
        if (opts.placeholder) el.placeholder = opts.placeholder;
        if (opts.type) el.type = opts.type;
        if (isTextarea) { el.textContent = value ?? ""; el.rows = 3; el.style.resize = "vertical"; }
        else el.value = value ?? "";
        el.addEventListener("input", e => { onChange(e.target.value); });
        return el;
    }
    function numField(value, onChange, opts = {}) {
        return editableField(value ?? "", v => onChange(v === "" ? null : Number(v)), { type: "number", ...opts });
    }
    function monthField(value, onChange, opts = {}) {
        const el = document.createElement("select");
        el.className = "we-edit-field form-select form-select-sm" + (opts.className ? " " + opts.className : "");
        el.appendChild(h("option", { value: "" }, "Mon"));
        for (let month = 1; month <= 12; month += 1) {
            el.appendChild(h("option", { value: String(month) }, MONTHS[month]));
        }
        el.value = value == null ? "" : String(value);
        el.addEventListener("change", e => onChange(e.target.value === "" ? null : Number(e.target.value)));
        return el;
    }
    function removeBtn(onClick) {
        return h("button", { className: "btn btn-sm btn-outline-danger we-remove-btn", onClick: e => { e.preventDefault(); onClick(); }, title: "Remove" },
            h("i", { className: "bi bi-x-lg" }));
    }
    function addBtn(label, onClick) {
        return h("button", { className: "btn btn-sm btn-outline-secondary we-add-btn", onClick: e => { e.preventDefault(); onClick(); } },
            h("i", { className: "bi bi-plus-lg me-1" }), label);
    }
    function dateFields(d) {
        return h("span", { className: "we-date-inline d-inline-flex gap-1 align-items-center" },
            numField(d.year, v => { d.year = v; }, { placeholder: "Year", className: "we-date-input" }),
            monthField(d.month, v => { d.month = v; }, { className: "we-date-input we-date-month" }));
    }
    function endDateFields(d) {
        const wrap = h("span", { className: "we-date-inline d-inline-flex gap-1 align-items-center" });
        const cb = h("input", { type: "checkbox", className: "form-check-input me-1" });
        cb.checked = !!d.present;
        const yf = numField(d.year, v => { d.year = v; }, { placeholder: "Year", className: "we-date-input" });
        const mf = monthField(d.month, v => { d.month = v; }, { className: "we-date-input we-date-month" });
        const tog = () => { yf.disabled = d.present; mf.disabled = d.present; };
        cb.addEventListener("change", () => { d.present = cb.checked; if (d.present) { d.year = null; d.month = null; yf.value = ""; mf.value = ""; } tog(); });
        tog();
        wrap.append(cb, h("label", { className: "form-check-label me-2", style: "font-size:0.8rem" }, "Present"), yf, mf);
        return wrap;
    }

    /* ── snapshot / restore ───────────────────────────────── */
    function takeSnapshot(key) {
        const parts = key.split('-');
        let value;
        if (key === 'summary') {
            value = { summary: data.summary, skills: data.skills };
        } else if (parts[0] === 'work' && parts.length === 2) {
            const e = data.work[+parts[1]];
            value = { employer: e.employer, start: e.start, end: e.end };
        } else if (parts[0] === 'work' && parts[2] === 'role') {
            value = data.work[+parts[1]].roles[+parts[3]];
        } else if (parts[0] === 'edu') {
            value = data.education[+parts[1]];
        } else if (parts[0] === 'pub') {
            value = data.publications[+parts[1]];
        }
        snapshots[key] = JSON.parse(JSON.stringify(value));
    }

    function restoreSnapshot(key) {
        const snap = snapshots[key];
        if (snap === null) { removeDataByKey(key); return; }
        const parts = key.split('-');
        const restored = JSON.parse(JSON.stringify(snap));
        if (key === 'summary') {
            data.summary = restored.summary;
            data.skills = restored.skills;
        } else if (parts[0] === 'work' && parts.length === 2) {
            const wi = +parts[1];
            data.work[wi].employer = restored.employer;
            data.work[wi].start = restored.start;
            data.work[wi].end = restored.end;
        } else if (parts[0] === 'work' && parts[2] === 'role') {
            data.work[+parts[1]].roles[+parts[3]] = restored;
        } else if (parts[0] === 'edu') {
            data.education[+parts[1]] = restored;
        } else if (parts[0] === 'pub') {
            data.publications[+parts[1]] = restored;
        }
    }

    function removeDataByKey(key) {
        const parts = key.split('-');
        if (parts[0] === 'work' && parts.length === 2) {
            data.work.splice(+parts[1], 1);
        } else if (parts[0] === 'work' && parts[2] === 'role') {
            data.work[+parts[1]].roles.splice(+parts[3], 1);
        } else if (parts[0] === 'edu') {
            data.education.splice(+parts[1], 1);
        } else if (parts[0] === 'pub') {
            data.publications.splice(+parts[1], 1);
        }
    }

    function moveRoleItem(role, fromIndex, toIndex) {
        if (!Array.isArray(role?.items)) return;
        if (fromIndex < 0 || toIndex < 0 || fromIndex >= role.items.length || toIndex >= role.items.length) return;
        if (fromIndex === toIndex) return;
        const [moved] = role.items.splice(fromIndex, 1);
        role.items.splice(toIndex, 0, moved);
    }

    function clearKeysWithPrefix(prefix) {
        for (const key of [...editingKeys]) {
            if (key === prefix || key.startsWith(prefix + '-')) {
                editingKeys.delete(key);
                delete snapshots[key];
            }
        }
    }

    /* ── per-item actions ─────────────────────────────────── */
    function startEdit(key, isNew = false) {
        if (isNew) snapshots[key] = null;
        else takeSnapshot(key);
        editingKeys.add(key);
        render();
    }

    function cancelItemEdit(key) {
        restoreSnapshot(key);
        editingKeys.delete(key);
        delete snapshots[key];
        clearKeysWithPrefix(key);
        render();
    }

    async function saveFull() {
        const resp = await fetch(`/api/candidates/${candidateId}/work-experience`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || resp.statusText);
        }
        await updateTokenCount();
        for (const k of [...editingKeys]) takeSnapshot(k);
    }

    async function saveItem(key) {
        try {
            await saveFull();
            editingKeys.delete(key);
            delete snapshots[key];
            showSavedBadge();
            render();
        } catch (e) {
            alert("Save failed: " + e.message);
        }
    }

    async function deleteAndSave(key) {
        removeDataByKey(key);
        editingKeys.delete(key);
        delete snapshots[key];
        // Clear sibling keys since indices shift after splice
        const parts = key.split('-');
        if (parts[0] === 'work' && parts.length === 2) clearKeysWithPrefix('work-');
        else if (parts[0] === 'work' && parts[2] === 'role') clearKeysWithPrefix(`work-${parts[1]}-role-`);
        else if (parts[0] === 'edu') clearKeysWithPrefix('edu-');
        else if (parts[0] === 'pub') clearKeysWithPrefix('pub-');
        try {
            await saveFull();
            showSavedBadge();
        } catch (e) { alert("Delete failed: " + e.message); }
        render();
    }

    function showSavedBadge() {
        const toastEl = document.getElementById("savedToast");
        if (toastEl) {
            const toast = bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 2000 });
            toast.show();
        }
    }

    /* ── per-item UI widgets ──────────────────────────────── */
    function initTooltips(root = document) {
        if (typeof bootstrap === "undefined" || !bootstrap.Tooltip) return;
        root.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => {
            if (!bootstrap.Tooltip.getInstance(el)) new bootstrap.Tooltip(el);
        });
    }

    function pencilBtn(key) {
        return h("button", {
            className: "btn btn-sm btn-link text-body-secondary p-0 ms-2 we-pencil-btn",
            onClick: e => {
                e.preventDefault();
                e.stopPropagation();
                startEdit(key);
            },
            "data-bs-toggle": "tooltip",
            "data-bs-placement": "bottom",
            "data-bs-title": "Edit",
            "aria-label": "Edit"
        }, h("i", { className: "bi bi-pencil", style: "font-size:0.75rem" }));
    }

    function editActionBtns(key, opts = {}) {
        const btns = [
            h("button", { className: "btn btn-sm btn-primary", onClick: e => { e.preventDefault(); saveItem(key); } },
                h("i", { className: "bi bi-check-lg me-1" }), "Save"),
            h("button", { className: "btn btn-sm btn-outline-secondary", onClick: e => { e.preventDefault(); cancelItemEdit(key); } },
                "Cancel")
        ];
        if (opts.canRemove) {
            btns.push(h("button", {
                className: "btn btn-sm btn-outline-danger ms-auto",
                onClick: e => { e.preventDefault(); if (confirm("Remove this item?")) deleteAndSave(key); }
            }, h("i", { className: "bi bi-trash" })));
        }
        return h("div", { className: "d-flex gap-1 align-items-center flex-wrap mt-2 mb-1 we-edit-actions" }, ...btns);
    }

    /* ══════════════════════════════════════════════════════
       RENDER – hybrid view/edit per item
       ══════════════════════════════════════════════════════ */

    function renderSummary() {
        const s = document.getElementById("summarySection");
        s.innerHTML = "";
        if (!data) return;
        const key = 'summary';

        if (editingKeys.has(key)) {
            s.append(h("div", { className: "card mb-4 we-editing" },
                h("div", { className: "card-body" },
                    h("h6", { className: "we-role-title mb-2" }, "Summary"),
                    editableField(data.summary, v => { data.summary = v; }, { multiline: true, placeholder: "Summary..." }),
                    h("h6", { className: "we-role-title mb-2 mt-3" }, "Skills"),
                    editableField(data.skills, v => { data.skills = v; }, { multiline: true, placeholder: "Skills..." }),
                    editActionBtns(key))));
        } else if (data.summary || data.skills) {
            const body = h("div", { className: "card-body" });
            body.append(h("div", { className: "d-flex justify-content-between align-items-start" },
                h("h6", { className: "we-role-title mb-2" }, "Summary"), pencilBtn(key)));
            if (data.summary) {
                const summary = h("div", { style: "font-size:0.85rem" });
                summary.innerHTML = parseMarkdownSafe(data.summary);
                body.append(summary);
            }
            if (data.skills) {
                const skills = h("div", { style: "font-size:0.85rem" });
                skills.innerHTML = parseMarkdownSafe(data.skills);
                body.append(h("h6", { className: "we-role-title mb-2 mt-3" }, "Skills"), skills);
            }
            s.append(h("div", { className: "card mb-4" }, body));
        }
    }

    function renderWork() {
        const s = document.getElementById("workSection");
        s.innerHTML = "";
        if (!data) return;

        if (!data.work || !data.work.length) {
            s.append(h("div", { className: "text-center text-body-secondary py-5" },
                h("i", { className: "bi bi-briefcase", style: "font-size:3rem" }),
                h("p", { className: "mt-3" }, "No work experience data available.")));
            s.append(addBtn("Work Entry", () => {
                data.work = data.work || [];
                data.work.push({ start: { year: new Date().getFullYear(), month: 1 }, end: { present: true },
                    employer: { name: "", description: "", link: "", sector: "", location: "" }, roles: [] });
                startEdit(`work-${data.work.length - 1}`, true);
            }));
            return;
        }

        const timeline = h("div", { className: "we-timeline" });
        data.work.forEach((entry, wi) => {
            const emp = entry.employer;
            const workKey = `work-${wi}`;
            const isEditingEmployer = editingKeys.has(workKey);

            // ── Employer header ──
            let header;
            if (isEditingEmployer) {
                header = h("div", { className: "card-header we-employer-header we-editing" },
                    h("div", { className: "d-flex justify-content-between align-items-start flex-wrap gap-2" },
                        h("div", { className: "flex-grow-1" },
                            editableField(emp.name, v => { emp.name = v; }, { placeholder: "Employer name", className: "fw-semibold mb-1" }),
                            h("div", { className: "d-flex flex-wrap gap-2" },
                                h("span", { className: "d-flex align-items-center gap-1" }, h("i", { className: "bi bi-building" }), editableField(emp.sector, v => { emp.sector = v; }, { placeholder: "Sector" })),
                                h("span", { className: "d-flex align-items-center gap-1" }, h("i", { className: "bi bi-geo-alt" }), editableField(emp.location, v => { emp.location = v; }, { placeholder: "Location" })))),
                        h("div", { className: "d-flex align-items-center gap-1" }, dateFields(entry.start), h("span", null, "—"), endDateFields(entry.end))),
                    editableField(emp.description, v => { emp.description = v; }, { multiline: true, placeholder: "Employer description", className: "mt-2" }),
                    editableField(emp.link, v => { emp.link = v; }, { placeholder: "Employer URL", className: "mt-1" }),
                    editActionBtns(workKey, { canRemove: true }));
            } else {
                header = h("div", { className: "card-header we-employer-header" },
                    h("div", { className: "d-flex justify-content-between align-items-start flex-wrap gap-2" },
                        h("div", null,
                            h("h5", { className: "mb-1" },
                                emp.link
                                    ? h("a", { href: emp.link, target: "_blank", className: "we-employer-link" }, emp.name, " ", h("i", { className: "bi bi-box-arrow-up-right", style: "font-size:0.75em" }))
                                    : emp.name,
                                pencilBtn(workKey)),
                            h("div", { className: "we-meta" },
                                emp.sector ? h("span", null, h("i", { className: "bi bi-building me-1" }), emp.sector) : null,
                                emp.location ? h("span", null, h("i", { className: "bi bi-geo-alt me-1" }), emp.location) : null)),
                        h("span", { className: "badge bg-primary we-date-badge" }, `${formatDate(entry.start)} — ${formatDate(entry.end)}`)));
                if (emp.description) header.append(h("p", { className: "mt-2 mb-0 text-body-secondary", style: "font-size:0.875rem" }, emp.description));
            }

            // ── Roles ──
            const rolesDiv = h("div", { className: "card-body p-0" });
            entry.roles.forEach((role, ri) => {
                const roleKey = `work-${wi}-role-${ri}`;

                if (editingKeys.has(roleKey)) {
                    const itemsC = h("div", { className: "we-items" });
                    role.items.forEach((item, ii) => {
                        itemsC.append(h("div", {
                            className: "we-item we-item-edit-draggable mb-3",
                            draggable: "true",
                            onDragstart: e => {
                                e.dataTransfer.effectAllowed = "move";
                                e.dataTransfer.setData("text/plain", String(ii));
                                e.currentTarget.classList.add("we-item-dragging");
                            },
                            onDragend: e => {
                                e.currentTarget.classList.remove("we-item-dragging");
                                document.querySelectorAll(".we-item-drop-target").forEach(el => el.classList.remove("we-item-drop-target"));
                            },
                            onDragover: e => {
                                const fromIndex = Number(e.dataTransfer.getData("text/plain"));
                                if (!Number.isInteger(fromIndex) || fromIndex === ii) return;
                                e.preventDefault();
                                e.currentTarget.classList.add("we-item-drop-target");
                            },
                            onDragleave: e => {
                                e.currentTarget.classList.remove("we-item-drop-target");
                            },
                            onDrop: e => {
                                e.preventDefault();
                                e.currentTarget.classList.remove("we-item-drop-target");
                                const fromIndex = Number(e.dataTransfer.getData("text/plain"));
                                if (!Number.isInteger(fromIndex) || fromIndex === ii) return;
                                moveRoleItem(role, fromIndex, ii);
                                render();
                            }
                        },
                            h("div", { className: "d-flex align-items-center gap-2 mb-1" },
                                h("span", { className: "we-item-drag-handle", title: "Drag to reorder work item" }, h("i", { className: "bi bi-grip-vertical" })),
                                editableField(item.title, v => { item.title = v; }, { placeholder: "Item title", className: "fw-semibold" }),
                                removeBtn(() => { role.items.splice(ii, 1); render(); })),
                            editableField(item.description, v => { item.description = v; }, { multiline: true, placeholder: "Description" }),
                            editableField(item.contribution, v => { item.contribution = v; }, { multiline: true, placeholder: "Contribution" })));
                    });
                    itemsC.append(h("div", { className: "mt-2" }, addBtn("Work Item", () => {
                        role.items.push({ title: "", description: "", contribution: "" }); render();
                    })));
                    rolesDiv.append(h("div", { className: "we-role we-editing" + (ri < entry.roles.length - 1 ? " border-bottom" : "") },
                        h("div", { className: "d-flex justify-content-between align-items-start flex-wrap gap-2 mb-2" },
                            h("div", { className: "flex-grow-1" },
                                editableField(role.title, v => { role.title = v; }, { placeholder: "Role title", className: "fw-semibold mb-1" }),
                                editableField(role.employment_type, v => { role.employment_type = v; }, { placeholder: "Employment type" })),
                            h("div", { className: "d-flex align-items-center gap-1" }, dateFields(role.start), h("span", null, "—"), endDateFields(role.end))),
                        itemsC,
                        editActionBtns(roleKey, { canRemove: true })));
                } else {
                    const rd = h("div", { className: "we-role" + (ri < entry.roles.length - 1 ? " border-bottom" : "") },
                        h("div", { className: "d-flex justify-content-between align-items-start flex-wrap gap-2 mb-2" },
                            h("div", null,
                                h("h6", { className: "mb-0 we-role-title" }, role.title, pencilBtn(roleKey)),
                                role.employment_type ? h("small", { className: "text-body-secondary" }, role.employment_type) : null),
                            h("small", { className: "badge bg-secondary we-date-badge" }, `${formatDate(role.start)} — ${formatDate(role.end)}`)));
                    if (role.items && role.items.length) {
                        const items = h("div", { className: "we-items" });
                        role.items.forEach((it, ii) => {
                            const itDiv = h("div", { className: "we-item" + (ii < role.items.length - 1 ? " mb-3" : "") });
                            if (it.title) itDiv.append(h("div", { className: "fw-semibold", style: "font-size:0.9rem" }, it.title));
                            if (it.description) {
                                const desc = h("div", { className: "text-body-secondary mb-1", style: "font-size:0.85rem" });
                                desc.innerHTML = parseMarkdownSafe(it.description);
                                itDiv.append(desc);
                            }
                            if (it.contribution) {
                                const contribution = h("div", { className: "mb-0", style: "font-size:0.85rem" });
                                contribution.innerHTML = parseMarkdownSafe(it.contribution);
                                itDiv.append(contribution);
                            }
                            items.append(itDiv);
                        });
                        rd.append(items);
                    }
                    rolesDiv.append(rd);
                }
            });

            // Add role button
            rolesDiv.append(h("div", { className: "p-3" + (entry.roles.length ? " border-top" : "") },
                addBtn("Role", () => {
                    entry.roles.push({ start: { year: new Date().getFullYear(), month: 1 }, end: { present: true }, title: "", employment_type: "", items: [] });
                    startEdit(`work-${wi}-role-${entry.roles.length - 1}`, true);
                })));

            timeline.append(h("div", { className: "card mb-4 we-entry" }, header, rolesDiv));
        });

        timeline.append(addBtn("Work Entry", () => {
            data.work.push({ start: { year: new Date().getFullYear(), month: 1 }, end: { present: true },
                employer: { name: "", description: "", link: "", sector: "", location: "" }, roles: [] });
            startEdit(`work-${data.work.length - 1}`, true);
        }));
        s.append(timeline);
    }

    function renderEducation() {
        const s = document.getElementById("educationSection");
        s.innerHTML = "";
        if (!data) return;

        if (!data.education || !data.education.length) {
            s.append(h("div", { className: "text-center text-body-secondary py-4" },
                h("p", { className: "mb-0" }, "No education data available.")));
        }

        (data.education || []).forEach((edu, ei) => {
            const key = `edu-${ei}`;

            if (editingKeys.has(key)) {
                const subjList = h("div", { className: "d-flex flex-wrap gap-1 mb-2" });
                (edu.subjects || []).forEach((sub, si) => {
                    subjList.append(h("span", { className: "d-inline-flex align-items-center gap-1" },
                        editableField(sub, v => { edu.subjects[si] = v; }, { placeholder: "Subject" }),
                        removeBtn(() => { edu.subjects.splice(si, 1); render(); })));
                });
                subjList.append(addBtn("Subject", () => { if (!edu.subjects) edu.subjects = []; edu.subjects.push(""); render(); }));

                let dissBlock = null;
                if (edu.dissertation) {
                    const d = edu.dissertation;
                    const advList = h("div", { className: "d-flex flex-wrap gap-1 mb-2" });
                    (d.advisors || []).forEach((a, ai) => {
                        advList.append(h("span", { className: "d-inline-flex align-items-center gap-1" },
                            editableField(a, v => { d.advisors[ai] = v; }, { placeholder: "Advisor" }),
                            removeBtn(() => { d.advisors.splice(ai, 1); render(); })));
                    });
                    advList.append(addBtn("Advisor", () => { if (!d.advisors) d.advisors = []; d.advisors.push(""); render(); }));
                    dissBlock = h("div", { className: "card-body" },
                        h("div", { className: "d-flex align-items-center gap-2 mb-2" },
                            h("h6", { className: "we-role-title mb-0" }, "Dissertation"),
                            removeBtn(() => { edu.dissertation = null; render(); })),
                        editableField(d.title, v => { d.title = v; }, { placeholder: "Title", className: "fw-semibold mb-1" }),
                        editableField(d.primary_research, v => { d.primary_research = v; }, { placeholder: "Primary research" }),
                        editableField(d.description, v => { d.description = v; }, { multiline: true, placeholder: "Description" }),
                        h("label", { className: "form-label mt-2", style: "font-size:0.8rem" }, "Advisors"), advList);
                }

                const cb = h("input", { type: "checkbox", className: "form-check-input" });
                cb.checked = edu.completed;
                cb.addEventListener("change", () => { edu.completed = cb.checked; });

                s.append(h("div", { className: "card mb-4 we-entry we-editing" },
                    h("div", { className: "card-header we-employer-header" },
                        h("div", { className: "d-flex justify-content-between align-items-start flex-wrap gap-2" },
                            h("div", { className: "flex-grow-1" },
                                editableField(edu.degree, v => { edu.degree = v; }, { placeholder: "Degree", className: "fw-semibold mb-1" }),
                                editableField(edu.institution, v => { edu.institution = v; }, { placeholder: "Institution" }),
                                subjList,
                                h("div", { className: "d-flex align-items-center gap-2" },
                                    h("span", { className: "d-flex align-items-center gap-1" }, h("i", { className: "bi bi-award" }), editableField(edu.GPA, v => { edu.GPA = v; }, { placeholder: "GPA" })),
                                    h("span", { className: "d-flex align-items-center gap-1" }, cb, h("label", { className: "form-check-label", style: "font-size:0.8rem" }, "Completed")))),
                            h("div", { className: "d-flex align-items-center gap-1" }, dateFields(edu.start), h("span", null, "—"), endDateFields(edu.end))),
                        editableField(edu.notes, v => { edu.notes = v; }, { placeholder: "Notes", className: "mt-2" }),
                        editActionBtns(key, { canRemove: true })),
                    dissBlock,
                    !edu.dissertation ? h("div", { className: "p-3 border-top" }, addBtn("Dissertation", () => {
                        edu.dissertation = { title: "", description: "", advisors: [], primary_research: "" }; render();
                    })) : null));
            } else {
                const subj = (edu.subjects || []).length ? " — " + edu.subjects.join(", ") : "";
                const header = h("div", { className: "card-header we-employer-header" },
                    h("div", { className: "d-flex justify-content-between align-items-start flex-wrap gap-2" },
                        h("div", null,
                            h("h5", { className: "mb-1" }, edu.degree + subj, pencilBtn(key)),
                            h("div", { className: "we-meta" },
                                h("span", null, h("i", { className: "bi bi-building me-1" }), edu.institution),
                                edu.GPA ? h("span", null, h("i", { className: "bi bi-award me-1" }), "GPA: " + edu.GPA) : null)),
                        h("span", { className: "badge bg-primary we-date-badge" }, `${formatDate(edu.start)} — ${formatDate(edu.end)}`)));
                if (!edu.completed) header.append(h("span", { className: "badge bg-warning text-dark mt-2" }, "Incomplete"));
                if (edu.notes) header.append(h("p", { className: "mt-2 mb-0 text-body-secondary", style: "font-size:0.875rem" }, edu.notes));

                let dissBlock = null;
                if (edu.dissertation) {
                    const d = edu.dissertation;
                    const description = d.description ? h("div", { className: "mt-2 mb-1", style: "font-size:0.85rem" }) : null;
                    if (description) description.innerHTML = parseMarkdownSafe(d.description);
                    dissBlock = h("div", { className: "card-body" },
                        h("h6", { className: "we-role-title mb-2" }, "Dissertation"),
                        h("div", { className: "fw-semibold", style: "font-size:0.9rem" }, d.title),
                        d.primary_research ? h("small", { className: "text-body-secondary" }, d.primary_research) : null,
                        description,
                        d.advisors && d.advisors.length ? h("p", { className: "mb-0 text-body-secondary", style: "font-size:0.85rem" },
                            h("i", { className: "bi bi-person me-1" }), "Advisors: " + d.advisors.join(", ")) : null);
                }
                s.append(h("div", { className: "card mb-4 we-entry" }, header, dissBlock));
            }
        });

        s.append(addBtn("Education", () => {
            if (!data.education) data.education = [];
            data.education.push({ start: { year: new Date().getFullYear(), month: 9 }, end: { year: new Date().getFullYear(), month: 6 },
                degree: "", institution: "", subjects: [], GPA: "", notes: "", completed: true });
            startEdit(`edu-${data.education.length - 1}`, true);
        }));
    }

    function renderPublications() {
        const s = document.getElementById("publicationsSection");
        s.innerHTML = "";
        if (!data) return;

        if (!data.publications || !data.publications.length) {
            s.append(h("div", { className: "text-center text-body-secondary py-4" },
                h("p", { className: "mb-0" }, "No publications data available.")));
        }

        (data.publications || []).forEach((pub, pi) => {
            const key = `pub-${pi}`;

            if (editingKeys.has(key)) {
                const authList = h("div", { className: "d-flex flex-wrap gap-1 mb-2" });
                (pub.authors || []).forEach((a, ai) => {
                    authList.append(h("span", { className: "d-inline-flex align-items-center gap-1" },
                        editableField(a.first_name, v => { a.first_name = v; }, { placeholder: "First" }),
                        editableField(a.last_name, v => { a.last_name = v; }, { placeholder: "Last" }),
                        removeBtn(() => { pub.authors.splice(ai, 1); render(); })));
                });
                authList.append(addBtn("Author", () => { if (!pub.authors) pub.authors = []; pub.authors.push({ first_name: "", last_name: "" }); render(); }));

                const linkList = h("div", { className: "d-flex flex-wrap gap-1 mb-2" });
                (pub.links || []).forEach((lnk, li) => {
                    linkList.append(h("span", { className: "d-inline-flex align-items-center gap-1" },
                        editableField(lnk, v => { pub.links[li] = v; }, { placeholder: "URL" }),
                        removeBtn(() => { pub.links.splice(li, 1); render(); })));
                });
                linkList.append(addBtn("Link", () => { if (!pub.links) pub.links = []; pub.links.push(""); render(); }));

                if (!pub.date) pub.date = { year: null, month: null, day: null };
                if (!pub.pages) pub.pages = { start: null, end: null };

                s.append(h("div", { className: "card mb-3 we-entry we-editing" },
                    h("div", { className: "card-body" },
                        editableField(pub.title, v => { pub.title = v; }, { placeholder: "Title", className: "fw-semibold mb-2" }),
                        h("label", { style: "font-size:0.8rem" }, "Authors"), authList,
                        h("div", { className: "d-flex flex-wrap gap-2 mb-2" },
                            h("span", { className: "d-flex align-items-center gap-1" }, h("small", null, "Year:"), numField(pub.date.year, v => { pub.date.year = v; }, { placeholder: "Year", className: "we-date-input" })),
                            h("span", { className: "d-flex align-items-center gap-1" }, h("small", null, "Mo:"), monthField(pub.date.month, v => { pub.date.month = v; }, { className: "we-date-input we-date-month" })),
                            h("span", { className: "d-flex align-items-center gap-1" }, h("small", null, "Day:"), numField(pub.date.day, v => { pub.date.day = v; }, { placeholder: "Day", className: "we-date-input we-date-month" }))),
                        h("div", { className: "d-flex flex-wrap gap-2 mb-2" },
                            editableField(pub.publication_name || "", v => { pub.publication_name = v; }, { placeholder: "Publication/journal" }),
                            numField(pub.volume, v => { pub.volume = v; }, { placeholder: "Vol" }),
                            numField(pub.issue, v => { pub.issue = v; }, { placeholder: "Issue" }),
                            numField(pub.pages.start, v => { pub.pages.start = v; }, { placeholder: "Page start" }),
                            numField(pub.pages.end, v => { pub.pages.end = v; }, { placeholder: "Page end" })),
                        h("div", { className: "d-flex flex-wrap gap-2 mb-2" },
                            editableField(pub.publisher, v => { pub.publisher = v; }, { placeholder: "Publisher" }),
                            editableField(pub.editor, v => { pub.editor = v; }, { placeholder: "Editor" }),
                            editableField(pub.doi, v => { pub.doi = v; }, { placeholder: "DOI" }),
                            numField(pub.isbn, v => { pub.isbn = v; }, { placeholder: "ISBN" })),
                        editableField(pub.abstract, v => { pub.abstract = v; }, { multiline: true, placeholder: "Abstract" }),
                        h("label", { style: "font-size:0.8rem" }, "Links"), linkList,
                        editActionBtns(key, { canRemove: true }))));
            } else {
                const dateStr = formatDate(pub.date);
                const authors = (pub.authors || []).map(a => `${a.first_name} ${a.last_name}`.trim()).filter(Boolean);
                const body = h("div", { className: "card-body" });

                const top = h("div", { className: "d-flex justify-content-between align-items-start flex-wrap gap-2 mb-2" });
                const topLeft = h("div");
                if (pub.title) topLeft.append(h("h6", { className: "we-role-title mb-1" }, pub.title, pencilBtn(key)));
                if (authors.length) topLeft.append(h("div", { className: "text-body-secondary", style: "font-size:0.85rem" }, authors.join(", ")));
                top.append(topLeft);
                if (dateStr) top.append(h("span", { className: "badge bg-primary we-date-badge" }, dateStr));
                body.append(top);

                const meta = h("div", { className: "we-pub-meta text-body-secondary", style: "font-size:0.85rem" });
                const pubName = pub.publication_name || pub.publication || pub.journal;
                if (pubName) meta.append(h("em", null, pubName), " ");
                if (pub.volume != null) meta.append(`vol.\u00a0${pub.volume}${pub.issue != null ? `(${pub.issue})` : ""} `);
                if (pub.pages && pub.pages.start != null && pub.pages.end != null) meta.append(`pp.\u00a0${pub.pages.start}–${pub.pages.end} `);
                if (pub.publisher) meta.append(`· ${pub.publisher} `);
                if (pub.editor) meta.append(`· Ed. ${pub.editor} `);
                body.append(meta);

                if (pub.abstract) {
                    const abstract = h("div", { className: "mt-1 mb-0", style: "font-size:0.85rem" });
                    abstract.innerHTML = parseMarkdownSafe(pub.abstract);
                    const det = h("details", { className: "mt-2" },
                        h("summary", { className: "text-body-secondary", style: "font-size:0.85rem;cursor:pointer" }, "Abstract"),
                        abstract);
                    body.append(det);
                }

                const links = h("div", { className: "mt-2", style: "font-size:0.85rem" });
                if (pub.doi) links.append(h("a", { href: `https://doi.org/${pub.doi}`, target: "_blank", className: "we-employer-link me-3" },
                    h("i", { className: "bi bi-link-45deg me-1" }), "DOI: " + pub.doi));
                (pub.links || []).forEach(lnk => links.append(h("a", { href: lnk, target: "_blank", className: "we-employer-link me-2" },
                    h("i", { className: "bi bi-box-arrow-up-right me-1" }), "Link")));
                body.append(links);

                s.append(h("div", { className: "card mb-3 we-entry" }, body));
            }
        });

        s.append(addBtn("Publication", () => {
            if (!data.publications) data.publications = [];
            data.publications.push({ title: "", abstract: "", authors: [], date: { year: null, month: null, day: null },
                publication_name: "", volume: null, issue: null,
                pages: { start: null, end: null }, publisher: "", editor: "", isbn: null, doi: "", links: [] });
            startEdit(`pub-${data.publications.length - 1}`, true);
        }));
    }

    /* ── main render ─────────────────────────────────────── */
    function render() {
        if (!data) return;
        renderSummary();
        renderWork();
        renderEducation();
        renderPublications();
        initTooltips();
    }

    /* ── save all (Ctrl+S) ───────────────────────────────── */
    async function saveAll() {
        if (editingKeys.size === 0) return;
        try {
            await saveFull();
            editingKeys.clear();
            Object.keys(snapshots).forEach(k => delete snapshots[k]);
            showSavedBadge();
            render();
        } catch (e) { alert("Save failed: " + e.message); }
    }

    async function exportProfile() {
        const resp = await fetch(`/api/candidates/${candidateId}/`);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || resp.statusText);
        }
        const blob = await resp.blob();
        const disposition = resp.headers.get("content-disposition") || "";
        const match = disposition.match(/filename="([^"]+)"/);
        const filename = match ? match[1] : `${candidateId}_work_experience.json`;
        const href = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = href;
        link.download = filename;
        document.body.append(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(href);
    }

    async function uploadProfile(file) {
        const formData = new FormData();
        formData.append("file", file);
        const resp = await fetch(`/api/candidates/${candidateId}/work-experience/upload`, {
            method: "POST",
            body: formData,
        });
        const body = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(body.detail || resp.statusText);
        data = body.profile;
        normalizePublicationFields();
        editingKeys.clear();
        Object.keys(snapshots).forEach(k => delete snapshots[k]);
        render();
        await updateTokenCount();
        showSavedBadge();
    }

    const nrTokensText = document.getElementById("nr-tokens");
    async function updateTokenCount() {
        if (!nrTokensText) return;
        if (!candidateId) {
            nrTokensText.textContent = "—";
            return;
        }
        nrTokensText.textContent = "...";
        try {
            const resp = await fetch(`/api/candidates/${candidateId}/work-experience/token-count`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const payload = await resp.json();
            nrTokensText.textContent = String(payload.nr_tokens ?? "—");
        } catch (e) {
            console.error(e);
            nrTokensText.textContent = "—";
        }
    }

    /* ── init ─────────────────────────────────────────────── */
    document.addEventListener("DOMContentLoaded", () => {
        const downloadBtn = document.getElementById("exportProfileBtn");
        const uploadBtn = document.getElementById("uploadProfileBtn");
        const uploadInput = document.getElementById("uploadProfileInput");
        normalizePublicationFields();
        updateTokenCount();
        if (downloadBtn) {
            downloadBtn.addEventListener("click", async () => {
                try {
                    await exportProfile();
                } catch (e) {
                    alert("Download failed: " + e.message);
                }
            });
        }
        if (uploadBtn && uploadInput) {
            uploadBtn.addEventListener("click", () => uploadInput.click());
            uploadInput.addEventListener("change", async () => {
                const [file] = uploadInput.files || [];
                if (!file) return;
                if (!confirm("Uploading JSON will overwrite the current work experience data in the database. Continue?")) {
                    uploadInput.value = "";
                    return;
                }
                try {
                    await uploadProfile(file);
                } catch (e) {
                    alert("Upload failed: " + e.message);
                } finally {
                    uploadInput.value = "";
                }
            });
        }
        render();
    });

    document.addEventListener("keydown", e => {
        if ((e.ctrlKey || e.metaKey) && e.key === "s") {
            e.preventDefault();
            saveAll();
        }
    });

    window.weEditor = { save: saveAll, render, startEdit, cancelItemEdit, saveItem };
})();
