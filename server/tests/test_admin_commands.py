from app.modules.runs.service import HELP_TEXT, process_admin_message


def test_casual_yes_does_not_approve_anything() -> None:
    outbound = process_admin_message(db=None, admin_wa_id="admin", text_body="yes")
    assert len(outbound) == 1
    assert outbound[0].text == HELP_TEXT


def test_casual_ok_does_not_approve_anything() -> None:
    outbound = process_admin_message(db=None, admin_wa_id="admin", text_body="ok approve it")
    assert outbound[0].text == HELP_TEXT


def test_approve_requires_exact_command_syntax() -> None:
    outbound = process_admin_message(
        db=None, admin_wa_id="admin", text_body="please approve RFQ-1042 thanks"
    )
    assert outbound[0].text == HELP_TEXT
