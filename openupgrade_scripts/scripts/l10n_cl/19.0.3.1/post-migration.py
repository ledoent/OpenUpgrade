from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "l10n_cl", "19.0.3.1/noupdate_changes.xml")
