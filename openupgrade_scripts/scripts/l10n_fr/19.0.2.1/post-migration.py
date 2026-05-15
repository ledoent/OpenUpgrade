from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "l10n_fr", "19.0.2.1/noupdate_changes.xml")
