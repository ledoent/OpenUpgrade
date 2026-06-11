from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # 19.0 drops the Cancelled stage in favour of kanban_state='cancel'.
    # event.event.stage_id is ondelete='restrict', so remap cancelled events
    # onto the surviving Ended stage (flagged cancelled) before removing the
    # stage; the safe helper also drops the ir_model_data row.
    cancelled = env.ref("event.event_stage_cancelled", raise_if_not_found=False)
    done = env.ref("event.event_stage_done", raise_if_not_found=False)
    if cancelled and done:
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE event_event
            SET stage_id = %s, kanban_state = 'cancel'
            WHERE stage_id = %s
            """,
            (done.id, cancelled.id),
        )
    openupgrade.delete_records_safely_by_xml_id(env, ["event.event_stage_cancelled"])
