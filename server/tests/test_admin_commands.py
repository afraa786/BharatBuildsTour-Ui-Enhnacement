from app.modules.runs.service import HELP_TEXT, process_admin_message


def test_casual_yes_does_not_approve_anything() -> None:
    outbound = process_admin_message(db=None, admin_wa_id="admin", text_body="yes")
    assert len(outbound) == 1
    assert outbound[0].text == HELP_TEXT


def test_casual_ok_prompts_for_exact_run_id() -> None:
    outbound = process_admin_message(db=None, admin_wa_id="admin", text_body="ok approve it")
    assert "exact RFQ ID" in outbound[0].text
    assert "Approve RFQ-1042" in outbound[0].text


def test_approve_requires_exact_command_syntax_and_returns_safe_prompt() -> None:
    outbound = process_admin_message(
        db=None, admin_wa_id="admin", text_body="please approve RFQ-1042 thanks"
    )
    assert "exact RFQ ID" in outbound[0].text
    assert "Approve RFQ-1042" in outbound[0].text
