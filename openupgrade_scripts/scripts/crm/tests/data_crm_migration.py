env = locals().get("env")

# Plant the stale menu action, rather than assume the seed already has one.
#
# The defect only exists in a database that came UP THROUGH an older version.
# 19.0 core declares crm_menu_root with no action at all -- name, web_icon,
# groups, sequence and nothing else (addons/crm/views/crm_menu_views.xml:9-14)
# -- and an earlier Odoo that DID ship action="crm.action_your_pipeline" leaves
# the value behind when 19.0 redeclares the menuitem without it. That is the
# same loader behaviour the post-migration script is written around: a
# menuitem redeclared without an action does not clear one.
#
# So a production copy upgraded from 18.0 carries the action, which is where
# this defect was measured, and a seed created fresh at 19.0 does not. The
# earlier version of this snippet asserted the action was present and aborted
# when it was not -- which on this seed stops the whole fixture batch before any
# other module's data is planted, and reports a missing precondition as though
# it were a broken migration.
#
# Planting it is both truer to the defect and what every other fixture here
# does: build the row that reaches the branch.
menu = env.ref("crm.crm_menu_root")
action = env.ref("crm.action_your_pipeline")
assert action._name == "ir.actions.server", (
    f"expected a server action for crm.action_your_pipeline, found {action._name}"
)

# Written as SQL for the same reason the migration reads it that way: `action`
# is a reference field, so assigning through the ORM goes via a recordset, and
# the point here is to leave a plain "model,id" string of the kind an older
# version left behind.
env.cr.execute(
    "UPDATE ir_ui_menu SET action = %s WHERE id = %s",
    (f"{action._name},{action.id}", menu.id),
)

env.cr.commit()
