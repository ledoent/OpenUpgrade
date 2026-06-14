from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """Clear the 'to-do' action path before the module data reloads.

    19.0 adds a unique ``ir.actions.path``. On a fresh install only the
    act_window ``project_task_action_todo`` owns 'to-do'; during migration the
    pre-existing server action also gets 'to-do' auto-populated, so when the
    window action's view data reloads it trips the cross-table uniqueness
    check. Null both here; the view data reload re-sets the window action.
    """
    for table in ("ir_act_window", "ir_act_server"):
        openupgrade.logged_query(
            env.cr, f"UPDATE {table} SET path = NULL WHERE path = 'to-do'"
        )
