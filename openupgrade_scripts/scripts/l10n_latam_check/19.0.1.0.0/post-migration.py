from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "l10n_latam_check", "19.0.1.0.0/noupdate_changes.xml")
