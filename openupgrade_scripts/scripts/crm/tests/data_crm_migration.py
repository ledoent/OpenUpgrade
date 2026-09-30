env = locals().get("env")

# The defect needs no planting -- 19.0 core puts an ir.actions.server on
# crm_menu_root by shipping action="crm.action_your_pipeline" on the menuitem.
# What this snippet does is refuse to let the test pass vacuously: if the seed
# ever stops carrying that action, the assertion after migration would hold for
# the wrong reason and report a fix that was never exercised.
menu = env.ref("crm.crm_menu_root")
assert menu.action, "crm_menu_root has no action, so the migration has nothing to clear"
assert menu.action._name == "ir.actions.server", (
    f"expected a server action on crm_menu_root, found {menu.action._name}"
)

env.cr.commit()
