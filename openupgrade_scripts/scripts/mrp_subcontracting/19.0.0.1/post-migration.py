from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "mrp_subcontracting", "19.0.0.1/noupdate_changes.xml")
