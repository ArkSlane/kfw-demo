import pytest


def test_format_steps_for_mcp_list_of_dicts(sample_test_case):
    from main import format_steps_for_mcp

    steps = sample_test_case["metadata"]["steps"]
    text = format_steps_for_mcp(steps)

    assert "1." in text
    assert "Navigate to login page" in text
    assert "Expected:" in text


def test_build_script_from_actions_log_parses_action_lines():
    from main import build_script_from_actions_log

    actions_taken = "\n".join(
        [
            "LLM Response: navigate(http://frontend:5173/)",
            "Action: navigate(http://frontend:5173/) - ok",
            "LLM Response: click(#login)",
            "Action: click(#login) - ok",
            "LLM Response: fill(input[name=\"username\"], testuser)",
            "Action: fill(input[name=\"username\"], testuser) - ok",
            "Action: wait(1500) - ok",
        ]
    )

    script = build_script_from_actions_log(actions_taken)

    assert "await page.goto('http://frontend:5173/');" in script
    assert "await page.click('#login');" in script
    assert "await page.fill('input[name=\"username\"]', 'testuser');" in script
    assert "await page.waitForTimeout(1500);" in script


def test_build_script_from_actions_log_ignores_non_action_lines():
    from main import build_script_from_actions_log

    script = build_script_from_actions_log("LLM Response: something")
    assert script.strip() == "// No actions captured"
