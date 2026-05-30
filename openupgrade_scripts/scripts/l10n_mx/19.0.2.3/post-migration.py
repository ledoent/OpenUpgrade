from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "l10n_mx", "19.0.2.3/noupdate_changes.xml")
