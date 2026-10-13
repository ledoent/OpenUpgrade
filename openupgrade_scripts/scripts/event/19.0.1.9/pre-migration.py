# Copyright 2026 Hunki Enterprises BV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_copy_columns = {
    "event_event": [
        ("badge_format", None, None),
    ]
}

_added_fields = [
    ("event_url", "event.event", "event_event", "char", None, "event"),
    ("is_default", "event.question", "event_question", "boolean", None, "event", False),
    (
        "is_reusable",
        "event.question",
        "event_question",
        "boolean",
        None,
        "event",
        False,
    ),
]


def event_event_badge_format(env):
    """
    Remap badge printer formats to four_per_sheet
    """
    openupgrade.map_values(
        env.cr,
        "badge_format",
        "badge_format",
        [("96x134", "four_per_sheet"), ("96x82", "four_per_sheet")],
        table="event_event",
    )


def remap_cancelled_stage(env):
    """
    19.0 drops the Cancelled stage in favour of kanban_state='cancel'.
    event.event.stage_id is ondelete='restrict', so remap cancelled events
    onto the surviving Ended stage (flagged cancelled) before removing the
    stage and its ir_model_data row. Pure SQL: event's models are not in
    the registry during its own pre-migration.
    """
    env.cr.execute(
        """
        SELECT name, res_id FROM ir_model_data
        WHERE module = 'event' AND model = 'event.stage'
          AND name IN ('event_stage_cancelled', 'event_stage_done')
        """
    )
    stages = dict(env.cr.fetchall())
    cancelled = stages.get("event_stage_cancelled")
    done = stages.get("event_stage_done")
    if not cancelled:
        return
    if done:
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE event_event
            SET stage_id = %s, kanban_state = 'cancel'
            WHERE stage_id = %s
            """,
            (done, cancelled),
        )
    openupgrade.logged_query(
        env.cr, "DELETE FROM event_stage WHERE id = %s", (cancelled,)
    )
    openupgrade.logged_query(
        env.cr,
        """
        DELETE FROM ir_model_data
        WHERE module = 'event' AND name = 'event_stage_cancelled'
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.copy_columns(env.cr, _copy_columns)
    openupgrade.add_fields(env, _added_fields)
    event_event_badge_format(env)
    remap_cancelled_stage(env)
