from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "l10n_ar", "19.0.3.7/noupdate_changes.xml")
