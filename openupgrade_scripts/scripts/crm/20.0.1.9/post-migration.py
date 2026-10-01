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
# WHY THIS KEYS ON IDENTITY AND NOT ON EXISTENCE
#
# The first version of this script asked "does the action this menu names still
# exist?" and returned early if it did. That can never fire. Odoo deletes
# obsolete ir_model_data records in a single sweep AFTER every migration stage
# has run -- post-migration AND end-migration -- so the target is always still
# present while any script can see it, and always gone by the time anything
# renders a menu. Measured on the 2026-10-01 prod-copy run:
#
#     15:18:13  crm post-migration runs, sees action 501, returns
#     15:18:58  every end-migration script runs (still too early)
#     15:19:41  Deleting 501@ir.actions.server (crm.action_your_pipeline)
#     15:20:03  Modules loaded
#
# So the condition is not "is it dangling yet" but "is it the record 20.0
# removes". We resolve crm.action_your_pipeline by xmlid -- which is still
# resolvable at this point, for exactly the same reason -- and clear the menu
# only when that is what it names. An installation that points its CRM root
# menu at something else is left alone, which was the original intent.
ACTION_TABLES = {
    "ir.actions.act_window": "ir_act_window",
    "ir.actions.server": "ir_act_server",
    "ir.actions.client": "ir_act_client",
    "ir.actions.report": "ir_act_report_xml",
}

# The record 20.0 drops, and the model it is declared as in 19.0.
DOOMED_ACTION_XMLID = "crm.action_your_pipeline"
DOOMED_ACTION_MODEL = "ir.actions.server"


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
    if model not in ACTION_TABLES or not res_id.isdigit():
        return
    res_id = int(res_id)

    # Case 1 -- the usual one: the menu still names the action 20.0 is about to
    # delete. Clear it now, because nothing later in the upgrade will.
    doomed = env.ref(DOOMED_ACTION_XMLID, raise_if_not_found=False)
    if doomed is not None and model == DOOMED_ACTION_MODEL and res_id == doomed.id:
        openupgrade.logged_query(
            env.cr,
            "UPDATE ir_ui_menu SET action = NULL WHERE id = %s",
            (menu.id,),
        )
        return

    # Case 2 -- the action is already gone (a re-run, or a database whose CRM
    # was set up differently and lost its action earlier). Still clear it: a
    # dangling reference breaks menu rendering whatever put it there.
    env.cr.execute(f"SELECT 1 FROM {ACTION_TABLES[model]} WHERE id = %s", (res_id,))
    if not env.cr.fetchone():
        openupgrade.logged_query(
            env.cr,
            "UPDATE ir_ui_menu SET action = NULL WHERE id = %s",
            (menu.id,),
        )
