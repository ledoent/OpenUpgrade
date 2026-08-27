from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "payment_mercado_pago", "19.0.1.0/noupdate_changes.xml")
