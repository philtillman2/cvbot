def _chat_input_position(page) -> str:
    return page.eval_on_selector(".chat-input-area", "el => getComputedStyle(el).position")


def _chat_input_wrapper_bottom_gap(page) -> float:
    return page.eval_on_selector(
        ".chat-input-wrapper",
        "el => window.innerHeight - el.getBoundingClientRect().bottom",
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
