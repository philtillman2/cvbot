def _chat_input_position(page) -> str:
    return page.eval_on_selector(".chat-input-area", "el => getComputedStyle(el).position")


def _chat_input_wrapper_bottom_gap(page) -> float:
    return page.eval_on_selector(
        ".chat-input-wrapper",
        "el => window.innerHeight - el.getBoundingClientRect().bottom",
    )


def _chat_messages_padding_bottom(page) -> float:
    return page.eval_on_selector(
        ".chat-messages",
        "el => parseFloat(getComputedStyle(el).paddingBottom)",
    )


def test_mobile_layout_applies_bottom_ui_fallback(browser, base_url):
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent=(
            "Mozilla/5.0 (Linux; Android 14; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36"
        ),
        is_mobile=True,
        has_touch=True,
    )
    page = context.new_page()
    try:
        page.goto(f"{base_url}/chat", wait_until="domcontentloaded")
        gap = _chat_input_wrapper_bottom_gap(page)
        assert _chat_input_position(page) == "fixed"
        assert 15 <= gap <= 70, f"Expected compact mobile bottom gap, got {gap}px"
    finally:
        context.close()


def test_viewport_inset_variable_increases_input_spacing(browser, base_url):
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent=(
            "Mozilla/5.0 (Linux; Android 14; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36"
        ),
        is_mobile=True,
        has_touch=True,
    )
    page = context.new_page()
    try:
        page.goto(f"{base_url}/chat", wait_until="domcontentloaded")
        baseline = _chat_input_wrapper_bottom_gap(page)
        page.evaluate("document.documentElement.style.setProperty('--viewport-bottom-inset', '120px')")
        updated = _chat_input_wrapper_bottom_gap(page)
        assert updated >= baseline + 25, (
            f"Expected viewport inset to increase input spacing (baseline={baseline}, updated={updated})"
        )
    finally:
        context.close()


def test_mobile_fallback_offset_variable_increases_spacing(browser, base_url):
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent=(
            "Mozilla/5.0 (Linux; Android 14; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36"
        ),
        is_mobile=True,
        has_touch=True,
    )
    page = context.new_page()
    try:
        page.goto(f"{base_url}/chat", wait_until="domcontentloaded")
        baseline = _chat_input_wrapper_bottom_gap(page)
        page.evaluate("document.documentElement.style.setProperty('--mobile-bottom-ui-offset', '72px')")
        updated = _chat_input_wrapper_bottom_gap(page)
        assert updated >= baseline + 20, (
            f"Expected fallback offset to increase spacing (baseline={baseline}, updated={updated})"
        )
    finally:
        context.close()


def test_mobile_messages_padding_tracks_composer_height(browser, base_url):
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent=(
            "Mozilla/5.0 (Linux; Android 14; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36"
        ),
        is_mobile=True,
        has_touch=True,
    )
    page = context.new_page()
    try:
        page.goto(f"{base_url}/chat", wait_until="domcontentloaded")
        baseline = _chat_messages_padding_bottom(page)
        page.eval_on_selector(
            "#chatInput",
            """el => {
                el.value = "a\\n".repeat(10);
                el.dispatchEvent(new Event("input", { bubbles: true }));
            }""",
        )
        # Wait for the requestAnimationFrame in syncBottomOffsets to fire
        page.evaluate("() => new Promise(r => requestAnimationFrame(r))")
        expanded = _chat_messages_padding_bottom(page)
        assert expanded >= baseline + 20, (
            f"Expected chat message bottom padding to grow with composer height (baseline={baseline}, expanded={expanded})"
        )
    finally:
        context.close()


def test_last_message_not_hidden_behind_mobile_composer(browser, base_url):
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent=(
            "Mozilla/5.0 (Linux; Android 14; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36"
        ),
        is_mobile=True,
        has_touch=True,
    )
    page = context.new_page()
    try:
        page.goto(f"{base_url}/chat", wait_until="domcontentloaded")
        page.evaluate(
            """() => {
                const messages = document.getElementById("chatMessages");
                const inputArea = document.querySelector(".chat-input-area");
                if (!messages || !inputArea) return;

                messages.querySelector(".welcome-screen")?.remove();
                for (let i = 0; i < 35; i += 1) {
                    const div = document.createElement("div");
                    div.className = "message message-assistant";
                    div.innerHTML = `<div class="message-content">Synthetic line ${i} `.repeat(4) + "</div>";
                    messages.appendChild(div);
                }
                messages.scrollTop = messages.scrollHeight;
            }"""
        )
        page.evaluate("() => window.dispatchEvent(new Event('resize'))")
        page.evaluate(
            "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
        )
        page.wait_for_timeout(300)
        page.wait_for_function(
            """() => {
                const messages = document.getElementById("chatMessages");
                const inputArea = document.querySelector(".chat-input-area");
                const last = messages?.lastElementChild?.getBoundingClientRect();
                const inputRect = inputArea?.getBoundingClientRect();
                if (!last || !inputRect) return false;
                return (last.bottom - inputRect.top) <= 1;
            }""",
            timeout=3000,
        )
        overlap = page.evaluate(
            """() => {
                const messages = document.getElementById("chatMessages");
                const inputArea = document.querySelector(".chat-input-area");
                const last = messages?.lastElementChild?.getBoundingClientRect();
                const inputRect = inputArea?.getBoundingClientRect();
                if (!last || !inputRect) return Number.POSITIVE_INFINITY;
                return last.bottom - inputRect.top;
            }"""
        )
        assert overlap <= 1, f"Expected final message to remain above composer, overlap={overlap}px"
    finally:
        context.close()
