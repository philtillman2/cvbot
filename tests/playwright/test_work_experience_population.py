import json
from pathlib import Path

import httpx


def test_work_experience_page_populates_candidate_data(browser, base_url):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    try:
        page.goto(f"{base_url}/work-experience", wait_until="domcontentloaded")
        candidate_id = page.evaluate("() => window.__candidateId")
        source = json.loads(Path("data/candidates/phil_tillman.json").read_text(encoding="utf-8"))
        payload = source["work_experience"]

        resp = httpx.put(
            f"{base_url}/api/candidates/{candidate_id}/work-experience",
            json=payload,
            timeout=20.0,
        )
        assert resp.status_code == 200

        page.goto(f"{base_url}/work-experience?candidate_id={candidate_id}", wait_until="domcontentloaded")
        data = page.evaluate("() => window.__profileData")
        assert data is not None, "Expected window.__profileData to be populated"
        assert data.get("summary") == payload["summary"]
        assert len(data.get("work", [])) == len(payload["work"])
        assert payload["summary"][:60] in page.inner_text("body")
        title = page.locator("h3").first.inner_text()
        assert "Tillman" in title, f"Expected candidate name in title, got: {title}"
    finally:
        context.close()
