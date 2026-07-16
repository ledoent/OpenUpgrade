# Copyright 2026 Hunki Enterprises BV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from openupgradelib import openupgrade


def chatbot_script_step_message(env):
    """
    Convert chatbot.script.step#message to html
    """
    openupgrade.copy_columns(env.cr, {"chatbot_script_step": [("message", None, None)]})
    openupgrade.convert_field_to_html(
        env.cr, "chatbot_script_step", "message", "message", translate=True
    )


def im_livechat_channel_rule_chatbot_enabled_condition(env):
    """
    Set im_livechat_channel_rule#chatbot_enabled_condition depending on
    chatbot_only_if_no_operator
    """
    env.cr.execute(
        """
        UPDATE
            im_livechat_channel_rule
        SET
            chatbot_enabled_condition='only_if_no_operator'
        WHERE
            chatbot_only_if_no_operator
        """
    )


def discuss_channel_livechat_end_dt(env):
    """19.0 replaces the ``livechat_active`` boolean with ``livechat_end_dt``.
    Without a backfill every historically closed session migrates as still
    open (multi-year durations, live status in the new dashboards). Clearing
    the status also satisfies CHECK(livechat_end_dt IS NULL OR livechat_status
    IS NULL)."""
    if not openupgrade.column_exists(env.cr, "discuss_channel", "livechat_active"):
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE discuss_channel
        SET livechat_end_dt = COALESCE(write_date, create_date),
            livechat_status = NULL
        WHERE channel_type = 'livechat'
          AND livechat_active IS NOT TRUE
          AND livechat_end_dt IS NULL
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "im_livechat", "19.0.1.0/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "im_livechat",
        [
            "livechat_email_template",
        ],
        ["body_html"],
    )
    chatbot_script_step_message(env)
    im_livechat_channel_rule_chatbot_enabled_condition(env)
    discuss_channel_livechat_end_dt(env)
