# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _clear_tracking_none(env):
    """19.0 spelled "track by quantity" as a selection key; 20.0 spells it False.

    19.0 declared product.template.tracking as serial / lot / none, required,
    defaulting to 'none'. 20.0 declares only lot and serial and says what the
    empty value means: "False on a storable product means it's tracked by
    quantity only."

    The column keeps whatever it held, so every product that was tracked by
    quantity comes out carrying 'none' -- a key the selection no longer
    declares. 184 of the seed's 197 products. It reads as an invalid value in
    the interface and matches neither branch of a domain over the field.
    """
    openupgrade.logged_query(
        env.cr,
        "UPDATE product_template SET tracking = NULL WHERE tracking = 'none'",
    )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "stock", "20.0.1.1/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "stock",
        ["mail_template_data_delivery_confirmation"],
        ["body_html"],
    )
    _clear_tracking_none(env)
