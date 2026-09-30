from openupgradelib import openupgrade

# The CRM root menu is left pointing at an action 20.0 deleted.
#
# 19.0's crm_menu_root carried action="crm.action_your_pipeline", an
# ir.actions.server. 20.0 redeclares the same menuitem with no action at all
# and drops action_your_pipeline entirely -- My Pipeline moved down to the
# child menu menu_crm_opportunities, on crm.crm_lead_action_pipeline.
#
# A menuitem redeclared without an action does not clear one: the data loader
# writes the fields the record carries, and `action` is not among them. So the
# upgrade deletes the server action and leaves ir_ui_menu.action naming it.
#
# That is not cosmetic. Anything that resolves a menu's action raises
# "Record does not exist or has been deleted" -- including website.layout, so
# EVERY frontend page 500s, /web/login included, and nobody can sign in.
# Measured on a 19.0 production copy: one stale row, and the whole website down.
#
# Written against the record rather than the id: which action a database has
# depends on how its CRM was set up, and an installation that already has no
# action here must not be touched.
ACTION_TABLES = {
    "ir.actions.act_window": "ir_act_window",
    "ir.actions.server": "ir_act_server",
    "ir.actions.client": "ir_act_client",
    "ir.actions.report": "ir_act_report_xml",
}


@openupgrade.migrate()
def migrate(env, version):
    menu = env.ref("crm.crm_menu_root", raise_if_not_found=False)
    if not menu:
        return
    # SQL, not menu.action: the field is a reference, so the ORM resolves it to
    # a recordset and there is no string left to inspect -- and resolving a
    # dangling one is the raise this script exists to prevent.
    env.cr.execute("SELECT action FROM ir_ui_menu WHERE id = %s", (menu.id,))
    action = env.cr.fetchone()[0]
    if not action:
        return
    model, _, res_id = action.partition(",")
    table = ACTION_TABLES.get(model)
    if not table or not res_id.isdigit():
        return
    env.cr.execute(f"SELECT 1 FROM {table} WHERE id = %s", (int(res_id),))
    if env.cr.fetchone():
        return
    openupgrade.logged_query(
        env.cr,
        "UPDATE ir_ui_menu SET action = NULL WHERE id = %s",
        (menu.id,),
    )
