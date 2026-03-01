import httpx
import json
import sqlite3
from pathlib import Path

TEST_CANDIDATE_ID = "philip_j_fry"


def test_work_experience_supports_all_editable_field_types(browser, base_url):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    try:
        seeded_candidate = json.loads(Path("data/candidates/phil_tillman.json").read_text(encoding="utf-8"))
        with sqlite3.connect("cvbot.db") as conn:
            conn.execute(
                "INSERT OR REPLACE INTO candidates (id, first_name, last_name, middle_name, work_experience) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    TEST_CANDIDATE_ID,
                    seeded_candidate.get("first_name", ""),
                    seeded_candidate.get("last_name", ""),
                    seeded_candidate.get("middle_name"),
                    json.dumps(seeded_candidate),
                ),
            )
            conn.commit()
        candidate_id = TEST_CANDIDATE_ID
        payload = {
            "summary": "Seed summary",
            "skills": "Seed skills",
            "work": [
                {
                    "start": {"year": 2020, "month": 1},
                    "end": {"year": 2022, "month": 12, "present": False},
                    "employer": {
                        "name": "Seed Employer",
                        "description": "Seed employer description",
                        "link": "",
                        "sector": "Software",
                        "location": "Remote",
                    },
                    "roles": [
                        {
                            "start": {"year": 2020, "month": 1},
                            "end": {"year": 2021, "month": 12, "present": False},
                            "title": "Engineer",
                            "employment_type": "Full-time",
                            "items": [
                                {
                                    "title": "Seed Item",
                                    "description": "Seed description",
                                    "contribution": "Seed contribution",
                                }
                            ],
                        }
                    ],
                }
            ],
            "education": [
                {
                    "start": {"year": 2016, "month": 9},
                    "end": {"year": 2019, "month": 6, "present": False},
                    "degree": "BSc",
                    "institution": "Seed University",
                    "subjects": ["Math"],
                    "GPA": "4.0",
                    "notes": "Seed notes",
                    "completed": True,
                    "dissertation": None,
                }
            ],
            "publications": [
                {
                    "title": "Seed publication",
                    "abstract": "Seed abstract",
                    "authors": [{"first_name": "A", "last_name": "B"}],
                    "date": {"year": 2021, "month": 5, "day": 1},
                    "publication_name": "Seed Journal",
                    "volume": 1,
                    "issue": 2,
                    "pages": {"start": 10, "end": 20},
                    "publisher": "Seed Publisher",
                    "editor": "Seed Editor",
                    "isbn": 1234567890,
                    "doi": "10.1000/seed",
                    "links": ["https://example.com"],
                }
            ],
        }

        resp = httpx.put(
            f"{base_url}/api/candidates/{candidate_id}/work-experience",
            json=payload,
            timeout=20.0,
        )
        assert resp.status_code == 200

        page.goto(f"{base_url}/work-experience?candidate_id={candidate_id}", wait_until="domcontentloaded")
        page.evaluate(
            """() => {
                window.weEditor.startEdit("summary");
                window.weEditor.startEdit("work-0");
                window.weEditor.startEdit("work-0-role-0");
                window.weEditor.startEdit("edu-0");
                window.weEditor.startEdit("pub-0");
            }"""
        )

        page.get_by_placeholder("Summary...").fill("Updated summary from textarea")
        page.get_by_placeholder("Employer name").fill("Updated employer from text input")
        page.get_by_placeholder("Publication/journal").fill("Updated publication name")
        page.locator("input.we-edit-field[type='number']").first.fill("2021")
        page.locator("select.we-edit-field.we-date-month").first.select_option("2")
        page.locator("label.form-check-label", has_text="Completed").locator(
            "xpath=preceding-sibling::input[1]"
        ).click()

        assert page.locator("input.we-edit-field").count() > 0
        assert page.locator("textarea.we-edit-field").count() > 0
        assert page.locator("input.we-edit-field[type='number']").count() > 0
        assert page.locator("select.we-edit-field.we-date-month").count() > 0
        assert page.locator("input.form-check-input[type='checkbox']").count() > 0

        profile = page.evaluate("() => window.__profileData")
        assert profile["summary"] == "Updated summary from textarea"
        assert profile["work"][0]["employer"]["name"] == "Updated employer from text input"
        assert profile["publications"][0]["publication_name"] == "Updated publication name"
        assert profile["work"][0]["start"]["year"] == 2021
        assert profile["work"][0]["start"]["month"] == 2
        assert profile["education"][0]["completed"] is False

        page.evaluate("() => window.weEditor.save()")
        saved_resp = httpx.get(f"{base_url}/api/candidates/{candidate_id}/", timeout=20.0)
        assert saved_resp.status_code == 200
        saved_work_experience = saved_resp.json()["work_experience"]
        assert saved_work_experience["summary"] == "Updated summary from textarea"
        assert saved_work_experience["work"][0]["employer"]["name"] == "Updated employer from text input"
        assert saved_work_experience["publications"][0]["publication_name"] == "Updated publication name"
        assert saved_work_experience["work"][0]["start"]["year"] == 2021
        assert saved_work_experience["work"][0]["start"]["month"] == 2
        assert saved_work_experience["education"][0]["completed"] is False

        page.goto(f"{base_url}/work-experience?candidate_id={candidate_id}", wait_until="domcontentloaded")
        reloaded = page.evaluate("() => window.__profileData")
        assert reloaded["summary"] == "Updated summary from textarea"
        assert reloaded["publications"][0]["publication_name"] == "Updated publication name"
    finally:
        context.close()
