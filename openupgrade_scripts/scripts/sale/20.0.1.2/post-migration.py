# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_legacy_sale_delay = openupgrade.get_legacy_name("sale_delay")


def _carry_the_invoicing_policy_default_onto_the_company(env):
    """20.0 gives the company a sale_invoice_policy; 19.0 kept it as an ir.default.

    The same shape as stock's shipping policy. 19.0's "Invoicing Policy" setting
    wrote an ir.default for product.template.invoice_policy, which is what a new
    product took. 20.0 adds res.company.sale_invoice_policy, required with
    default="order" (sale/models/res_company.py:81-83), and the upgrade stamps
    "order" on every company.

    So a company invoicing on delivered quantities starts defaulting new
    products to ordered quantities instead -- which invoices goods before they
    ship. Existing products are unaffected; they carry their own
    invoice_policy, which survives.

    Measured on the sanitised prod copy: the ir.default is "order", which is
    also 20.0's default, so this data cannot show the difference. The migration
    test plants the disagreement.
    """
    if not openupgrade.table_exists(env.cr, "ir_default"):
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE res_company c
        SET sale_invoice_policy = d.value
        FROM (
            SELECT comp.id AS company_id, (
                SELECT dd.json_value::jsonb #>> '{}'
                FROM ir_default dd
                JOIN ir_model_fields f ON f.id = dd.field_id
                JOIN ir_model m ON m.id = f.model_id
                WHERE m.model = 'product.template' AND f.name = 'invoice_policy'
                  AND (dd.company_id = comp.id OR dd.company_id IS NULL)
                ORDER BY dd.company_id NULLS LAST
                LIMIT 1
            ) AS value
            FROM res_company comp
        ) d
        WHERE d.company_id = c.id
          AND d.value IN ('order', 'delivery')
          AND c.sale_invoice_policy IS DISTINCT FROM d.value
        """,
    )
    if env.cr.rowcount:
        openupgrade.message(
            env.cr,
            "sale",
            False,
            False,
            "res.company: carried the 19.0 invoicing-policy default onto %s "
            "company(ies); 20.0 moved the setting onto the company, where its "
            "'order' default would invoice new products before delivery",
            env.cr.rowcount,
        )


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
    # Before the early return below: that guard is about the sale_delay
    # column, and letting it skip this carry would make the company policy
    # depend on an unrelated field still being present.
    _carry_the_invoicing_policy_default_onto_the_company(env)
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
