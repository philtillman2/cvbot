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

    let conversationId = null;

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

    // Scroll to bottom
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Render markdown in existing messages
    document.querySelectorAll(".message-assistant .message-content").forEach((el) => {
        if (typeof marked !== "undefined") {
            el.innerHTML = marked.parse(el.textContent);
        }
    });
    scrollToBottom();

    // Send message
    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text || !conversationId) return;

        // Add user message to UI
        appendMessage("user", text);
        chatInput.value = "";
        chatInput.style.height = "auto";
        sendBtn.disabled = true;
        chatInput.disabled = true;

        // Create assistant placeholder
        const assistantDiv = appendMessage("assistant", "");
        assistantDiv.querySelector(".message-content").classList.add("streaming-cursor");

        try {
            const resp = await fetch(`/api/chat/${conversationId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: text,
                    model: modelSelect.value,
                }),
            });

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
                        if (data.type === "token") {
                            fullText += data.content;
                            const contentEl = assistantDiv.querySelector(".message-content");
                            if (typeof marked !== "undefined") {
                                contentEl.innerHTML = marked.parse(fullText);
                            } else {
                                contentEl.textContent = fullText;
                            }
                            scrollToBottom();
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
            assistantDiv.querySelector(".message-content").textContent =
                "Error: " + err.message;
            assistantDiv.querySelector(".message-content").classList.remove("streaming-cursor");
        }

        sendBtn.disabled = false;
        chatInput.disabled = false;
        chatInput.focus();
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
        chatMessages.appendChild(div);
        scrollToBottom();
        return div;
    }
});
