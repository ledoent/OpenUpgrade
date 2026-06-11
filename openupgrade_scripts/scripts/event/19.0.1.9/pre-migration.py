from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # 19.0 drops the Cancelled stage in favour of kanban_state='cancel'.
    # event.event.stage_id is ondelete='restrict', so remap cancelled events
    # onto the surviving Ended stage (flagged cancelled) before removing the
    # stage and its ir_model_data row. Pure SQL: event's models are not in
    # the registry during its own pre-migration, so env.ref cannot be used.
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
