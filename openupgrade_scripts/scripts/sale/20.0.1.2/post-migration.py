# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_legacy_sale_delay = openupgrade.get_legacy_name("sale_delay")


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "sale", "20.0.1.2/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "sale",
        ["email_template_proforma"],
        ["body_html", "description", "name", "subject"],
    )
    openupgrade.delete_record_translations(
        env.cr,
        "sale",
        ["email_template_edi_sale", "mail_template_sale_confirmation"],
        ["body_html", "subject"],
    )
    # The 19.0 value was global, so it holds for every company. A missing key
    # means the field default, which is 0, so zeroes need no row.
    if not openupgrade.column_exists(env.cr, "product_template", _legacy_sale_delay):
        return
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE product_template pt
        SET sale_delay = (
            SELECT jsonb_object_agg(company.id::text, pt.{_legacy_sale_delay})
            FROM res_company company
        )
        WHERE pt.{_legacy_sale_delay} IS NOT NULL
          AND pt.{_legacy_sale_delay} != 0
        """,
    )
