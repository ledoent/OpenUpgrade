from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "l10n_sa", "19.0.2.2/noupdate_changes.xml")
