from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "sale_gelato", "19.0.1.0/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "sale_gelato",
        [
            "order_status_update",
        ],
    )
