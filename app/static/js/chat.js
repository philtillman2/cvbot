document.addEventListener("DOMContentLoaded", () => {
    const chatMessages = document.getElementById("chatMessages");
    const chatInput = document.getElementById("chatInput");
    const sendBtn = document.getElementById("sendBtn");
    const newChatBtn = document.getElementById("newChatBtn");
    const candidateSelect = document.getElementById("candidateSelect");
    const modelSelect = document.getElementById("modelSelect");
    const searchThreads = document.getElementById("searchThreads");
    const sidebar = document.getElementById("sidebar");
    const openSidebar = document.getElementById("openSidebar");
    const closeSidebar = document.getElementById("closeSidebar");
    const usageSummary = document.getElementById("chatUsageSummary");
    const usageTokenText = document.getElementById("chatUsageTokenText");
    const usageProgressBar = document.getElementById("chatUsageProgressBar");
    const usageCurrentCost = document.getElementById("chatUsageCurrentCost");
    const usageMaxCost = document.getElementById("chatUsageMaxCost");

    let conversationId = null;
    let editingMessageId = null;

    // Extract conversation ID from URL
    const pathMatch = window.location.pathname.match(/^\/chat\/(\d+)$/);
    if (pathMatch) {
        conversationId = parseInt(pathMatch[1]);
    }

    // Auto-resize textarea
    chatInput.addEventListener("input", () => {
        chatInput.style.height = "auto";
        chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + "px";
    });

    // Send on Enter (Shift+Enter for newline)
    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener("click", sendMessage);

    // New Chat
    newChatBtn.addEventListener("click", async () => {
        const candidateId = candidateSelect.value;
        if (!candidateId) return;

        const resp = await fetch("/api/conversations", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ candidate_id: candidateId }),
        });
        const conv = await resp.json();
        window.location.href = `/chat/${conv.id}`;
    });

    // Delete conversation
    document.querySelectorAll(".delete-conv").forEach((btn) => {
        btn.addEventListener("click", async (e) => {
            e.preventDefault();
            e.stopPropagation();
            const id = btn.dataset.id;
            await fetch(`/api/conversations/${id}`, { method: "DELETE" });
            window.location.href = "/chat";
        });
    });

    function startInlineRename(item, id) {
        const titleEl = item?.querySelector(".conv-title");
        if (!titleEl || !id || titleEl.dataset.editing === "true") return;
        titleEl.dataset.editing = "true";
        titleEl.dataset.originalTitle = titleEl.textContent.trim() || "New Chat";
        titleEl.setAttribute("contenteditable", "true");
        titleEl.classList.add("editing");
        titleEl.focus();
        const range = document.createRange();
        range.selectNodeContents(titleEl);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
    }

    async function finishInlineRename(titleEl, save) {
        if (!titleEl || titleEl.dataset.editing !== "true" || titleEl.dataset.saving === "true") return;
        titleEl.dataset.saving = "true";
        const item = titleEl.closest(".conversation-item");
        const id = item?.dataset?.id;
        const originalTitle = titleEl.dataset.originalTitle || "New Chat";
        const nextTitle = titleEl.textContent.trim();
        titleEl.removeAttribute("contenteditable");
        titleEl.classList.remove("editing");
        titleEl.dataset.editing = "false";
        if (!save || !nextTitle || nextTitle === originalTitle || !id) {
            titleEl.textContent = originalTitle;
            titleEl.dataset.saving = "false";
            return;
        }
        const resp = await fetch(`/api/conversations/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: nextTitle }),
        });
        if (!resp.ok) {
            titleEl.textContent = originalTitle;
            alert("Unable to rename chat.");
            titleEl.dataset.saving = "false";
            return;
        }
        const conv = await resp.json();
        titleEl.textContent = conv.title || "New Chat";
        titleEl.dataset.saving = "false";
    }

    const titleClickTimers = new WeakMap();

    // Rename conversation
    document.querySelectorAll(".rename-conv").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            startInlineRename(btn.closest(".conversation-item"), btn.dataset.id);
        });
    });
    document.querySelectorAll(".conversation-item .conv-title").forEach((titleEl) => {
        titleEl.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            const item = titleEl.closest(".conversation-item");
            if (!item || titleEl.dataset.editing === "true") return;
            if (e.detail === 1) {
                const timer = setTimeout(() => {
                    window.location.href = item.getAttribute("href");
                }, 220);
                titleClickTimers.set(titleEl, timer);
                return;
            }
            const timer = titleClickTimers.get(titleEl);
            if (timer) {
                clearTimeout(timer);
                titleClickTimers.delete(titleEl);
            }
            startInlineRename(item, item?.dataset?.id);
        });
        titleEl.addEventListener("keydown", async (e) => {
            if (titleEl.dataset.editing !== "true") return;
            if (e.key === "Enter") {
                e.preventDefault();
                await finishInlineRename(titleEl, true);
            } else if (e.key === "Escape") {
                e.preventDefault();
                await finishInlineRename(titleEl, false);
            }
        });
        titleEl.addEventListener("blur", async () => {
            await finishInlineRename(titleEl, true);
        });
    });

    // Search threads
    searchThreads.addEventListener("input", () => {
        const q = searchThreads.value.toLowerCase();
        document.querySelectorAll(".conversation-item").forEach((item) => {
            const title = item.querySelector(".conv-title").textContent.toLowerCase();
            item.style.display = title.includes(q) ? "" : "none";
        });
    });

    // Mobile sidebar
    openSidebar?.addEventListener("click", () => sidebar.classList.add("open"));
    closeSidebar?.addEventListener("click", () => sidebar.classList.remove("open"));

    // Edit user messages
    chatMessages.addEventListener("click", (e) => {
        const btn = e.target.closest(".edit-message");
        if (btn) {
            if (sendBtn.disabled) return;
            e.preventDefault();
            const messageDiv = btn.closest(".message-user");
            if (!messageDiv?.dataset?.messageId) return;
            if (btn.dataset.mode === "editing") {
                submitInlineEdit(messageDiv);
            } else {
                startInlineEdit(messageDiv);
            }
            return;
        }
        const cancelBtn = e.target.closest(".cancel-edit-message");
        if (!cancelBtn || sendBtn.disabled) return;
        e.preventDefault();
        const messageDiv = cancelBtn.closest(".message-user");
        if (!messageDiv) return;
        finishInlineEdit(messageDiv, false);
    });

    // Scroll to bottom
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function updateUsageSummary(usage) {
        const dailyLimit = usage.daily_limit_usd || 0;
        const dailyTotal = usage.daily_total_usd || 0;
        const pct = dailyLimit > 0 ? Math.min((dailyTotal / dailyLimit) * 100, 100) : 0;
        usageSummary?.classList.remove("d-none");
        if (usageTokenText) {
            usageTokenText.textContent =
                `${usage.input_tokens} in / ${usage.output_tokens} out tokens`;
        }
        if (usageCurrentCost) usageCurrentCost.textContent = `$${dailyTotal.toFixed(2)}`;
        if (usageMaxCost) usageMaxCost.textContent = `$${dailyLimit.toFixed(2)}`;
        if (usageProgressBar) {
            usageProgressBar.style.width = `${pct}%`;
            usageProgressBar.setAttribute("aria-valuenow", String(pct));
        }
    }

    async function initializeUsageSummary() {
        try {
            const resp = await fetch("/api/costs/today");
            if (!resp.ok) return;
            const usage = await resp.json();
            updateUsageSummary({ ...usage, input_tokens: 0, output_tokens: 0 });
        } catch (_) {}
    }

    // Render markdown in existing messages
    document.querySelectorAll(".message-assistant .message-content").forEach((el) => {
        if (typeof marked !== "undefined") {
            el.innerHTML = marked.parse(el.textContent);
        }
    });
    initializeUsageSummary();
    scrollToBottom();

    // Send message
    async function sendMessage(overrideText = null) {
        const text = (overrideText ?? chatInput.value).trim();
        if (!text || !conversationId) return;
        const isEdit = editingMessageId !== null;
        const endpoint = isEdit
            ? `/api/chat/${conversationId}/edit/${editingMessageId}`
            : `/api/chat/${conversationId}`;
        let userDiv = null;
        let originalUserText = "";
        const removedTail = [];

        if (isEdit) {
            userDiv = chatMessages.querySelector(`.message-user[data-message-id="${editingMessageId}"]`);
            if (!userDiv) {
                editingMessageId = null;
                return;
            }
            const userContent = userDiv.querySelector(".message-content");
            originalUserText = userContent?.textContent || "";
            if (userContent) userContent.textContent = text;
            let next = userDiv.nextElementSibling;
            while (next) {
                const following = next.nextElementSibling;
                removedTail.push(next);
                next.remove();
                next = following;
            }
        } else {
            userDiv = appendMessage("user", text);
        }
        if (!isEdit) {
            chatInput.value = "";
            chatInput.style.height = "auto";
        }
        sendBtn.disabled = true;
        chatInput.disabled = true;

        // Create assistant placeholder
        const assistantDiv = appendMessage("assistant", "");
        assistantDiv.querySelector(".message-content").classList.add("streaming-cursor");

        try {
            const resp = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: text,
                    model: modelSelect.value,
                }),
            });
            if (!resp.ok || !resp.body) {
                let errorMessage = "Failed to send message";
                try {
                    const payload = await resp.json();
                    if (payload?.error) errorMessage = payload.error;
                } catch (e) {}
                throw new Error(errorMessage);
            }

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let fullText = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split("\n");

                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    const dataStr = line.slice(6).trim();
                    if (dataStr === "[DONE]") continue;

                    try {
                        const data = JSON.parse(dataStr);
                        if (data.type === "user_message" && data.message_id && userDiv) {
                            userDiv.dataset.messageId = String(data.message_id);
                            ensureEditButton(userDiv);
                        } else if (data.type === "token") {
                            fullText += data.content;
                            const contentEl = assistantDiv.querySelector(".message-content");
                            if (typeof marked !== "undefined") {
                                contentEl.innerHTML = marked.parse(fullText);
                            } else {
                                contentEl.textContent = fullText;
                            }
                            scrollToBottom();
                        } else if (data.type === "usage") {
                            updateUsageSummary(data);
                        }
                    } catch (e) {
                        // skip malformed chunks
                    }
                }
            }

            // Remove streaming cursor
            assistantDiv.querySelector(".message-content").classList.remove("streaming-cursor");

            // Final markdown render
            const contentEl = assistantDiv.querySelector(".message-content");
            if (typeof marked !== "undefined" && fullText) {
                contentEl.innerHTML = marked.parse(fullText);
            }
        } catch (err) {
            if (isEdit && userDiv) {
                const userContent = userDiv.querySelector(".message-content");
                if (userContent) userContent.textContent = originalUserText;
                assistantDiv.remove();
                removedTail.forEach((node) => chatMessages.appendChild(node));
                alert(err.message);
            } else {
                assistantDiv.querySelector(".message-content").textContent =
                    "Error: " + err.message;
                assistantDiv.querySelector(".message-content").classList.remove("streaming-cursor");
            }
        } finally {
            if (isEdit) editingMessageId = null;
        }

        sendBtn.disabled = false;
        chatInput.disabled = false;
        chatInput.focus();
    }

    function startInlineEdit(messageDiv) {
        const active = chatMessages.querySelector(".message-user.inline-editing");
        if (active && active !== messageDiv) {
            finishInlineEdit(active, false);
        }
        const contentEl = messageDiv.querySelector(".message-content");
        const editBtn = messageDiv.querySelector(".edit-message");
        if (!contentEl || !editBtn) return;
        messageDiv.dataset.originalContent = contentEl.textContent || "";
        messageDiv.classList.add("inline-editing");
        contentEl.setAttribute("contenteditable", "true");
        contentEl.focus();
        const range = document.createRange();
        range.selectNodeContents(contentEl);
        range.collapse(false);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        editBtn.dataset.mode = "editing";
        editBtn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Save';
        ensureCancelEditButton(messageDiv);
    }

    function finishInlineEdit(messageDiv, keepChanges) {
        const contentEl = messageDiv?.querySelector(".message-content");
        const editBtn = messageDiv?.querySelector(".edit-message");
        if (!contentEl || !editBtn) return;
        if (!keepChanges) {
            contentEl.textContent = messageDiv.dataset.originalContent || contentEl.textContent;
            editingMessageId = null;
        }
        contentEl.removeAttribute("contenteditable");
        messageDiv.classList.remove("inline-editing");
        editBtn.dataset.mode = "";
        editBtn.innerHTML = '<i class="bi bi-pencil-square me-1"></i>Edit';
        messageDiv.querySelector(".cancel-edit-message")?.remove();
    }

    async function submitInlineEdit(messageDiv) {
        const contentEl = messageDiv.querySelector(".message-content");
        if (!contentEl) return;
        const text = contentEl.textContent.trim();
        if (!text) return;
        editingMessageId = parseInt(messageDiv.dataset.messageId);
        finishInlineEdit(messageDiv, true);
        await sendMessage(text);
    }

    function appendMessage(role, content) {
        // Remove welcome screen if present
        const welcome = chatMessages.querySelector(".welcome-screen");
        if (welcome) welcome.remove();

        const div = document.createElement("div");
        div.className = `message message-${role}`;
        const contentDiv = document.createElement("div");
        contentDiv.className = "message-content";

        if (role === "assistant" && typeof marked !== "undefined" && content) {
            contentDiv.innerHTML = marked.parse(content);
        } else {
            contentDiv.textContent = content;
        }

        div.appendChild(contentDiv);
        if (role === "user") {
            ensureEditButton(div);
        }
        chatMessages.appendChild(div);
        scrollToBottom();
        return div;
    }

    function ensureEditButton(messageDiv) {
        if (!messageDiv || messageDiv.querySelector(".edit-message")) return;
        const btn = document.createElement("button");
        btn.className = "btn btn-link btn-sm edit-message p-0 mt-1 text-white";
        btn.innerHTML = '<i class="bi bi-pencil-square me-1"></i>Edit';
        messageDiv.appendChild(btn);
    }

    function ensureCancelEditButton(messageDiv) {
        if (!messageDiv || messageDiv.querySelector(".cancel-edit-message")) return;
        const btn = document.createElement("button");
        btn.className = "btn btn-link btn-sm cancel-edit-message p-0 mt-1 ms-2 text-white";
        btn.innerHTML = '<i class="bi bi-x-lg me-1"></i>Cancel';
        messageDiv.appendChild(btn);
    }
});
