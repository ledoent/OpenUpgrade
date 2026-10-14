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


def _carry_the_shipping_policy_default_onto_the_company(env):
    """20.0 gives the company a picking_policy; 19.0 kept it as an ir.default.

    19.0 had no company field at all. The "Shipping Policy" setting on the Sales
    configuration page wrote an ir.default for sale.order.picking_policy, which
    is how a new order got its value. 20.0 adds res.company.picking_policy,
    required with default='direct' (stock/models/res_company.py:56-59).

    So the upgrade stamps 'direct' on every company, and a company that had
    chosen "When all products are ready" silently starts shipping partial
    orders. Nothing fails: the column is populated either way.

    Measured on the sanitised prod copy: the ir.default is "direct", which is
    also 20.0's default -- the two agree by coincidence, which is exactly why
    this would pass unnoticed. The migration test plants the disagreement.

    A company-specific ir.default wins over a global one, which is the order
    19.0 itself resolved them in. The guard is a comparison, not a NULL check:
    the column is required and already holds the default.
    """
    if not openupgrade.table_exists(env.cr, "ir_default"):
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE res_company c
        SET picking_policy = d.value
        FROM (
            SELECT comp.id AS company_id, (
                SELECT dd.json_value::jsonb #>> '{}'
                FROM ir_default dd
                JOIN ir_model_fields f ON f.id = dd.field_id
                JOIN ir_model m ON m.id = f.model_id
                WHERE m.model = 'sale.order' AND f.name = 'picking_policy'
                  AND (dd.company_id = comp.id OR dd.company_id IS NULL)
                ORDER BY dd.company_id NULLS LAST
                LIMIT 1
            ) AS value
            FROM res_company comp
        ) d
        WHERE d.company_id = c.id
          AND d.value IN ('direct', 'one')
          AND c.picking_policy IS DISTINCT FROM d.value
        """,
    )
    if env.cr.rowcount:
        openupgrade.message(
            env.cr,
            "stock",
            False,
            False,
            "res.company: carried the 19.0 shipping-policy default onto %s "
            "company(ies); 20.0 moved the setting onto the company and its "
            "'direct' default would have started shipping partial orders",
            env.cr.rowcount,
        )


def _settle_the_move_line_date_against_its_move(env):
    """20.0 makes stock.move.line.date a STORED related to move_id.date.

    19.0 stored the line's own date, which could differ from the move's. 20.0
    declares `date = fields.Datetime('Date', related="move_id.date",
    store=True)` (stock_move_line.py:61-62), so the two are no longer allowed to
    disagree -- but the column already exists, so the upgrade recomputes nothing
    and the disagreement survives.

    That is a time bomb rather than a loss: the next write that touches the move
    recomputes the related and overwrites every such line, silently, whenever
    that happens to be. Measured on the 585-module seed: 65 of 122 move lines
    hold a date their move does not.

    Aligning them here makes the change visible now, with a count, instead of
    weeks later with none. The lines whose own date is discarded are reported,
    because that date was real information in 19.0 and the report is the only
    record left of it.
    """
    env.cr.execute(
        """
        SELECT count(*) FROM stock_move_line l
        JOIN stock_move m ON m.id = l.move_id
        WHERE l.date IS DISTINCT FROM m.date
        """
    )
    disagreeing = env.cr.fetchone()[0]
    if not disagreeing:
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE stock_move_line l
        SET date = m.date
        FROM stock_move m
        WHERE m.id = l.move_id AND l.date IS DISTINCT FROM m.date
        """,
    )
    openupgrade.message(
        env.cr,
        "stock",
        False,
        False,
        "stock.move.line: %s line(s) carried a date their move did not. 20.0 "
        "stores that field as a related to move_id.date, so the values could "
        "not both survive; they were aligned to the move now rather than being "
        "overwritten by the first recompute that happened to run",
        disagreeing,
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
    _carry_the_shipping_policy_default_onto_the_company(env)
    _settle_the_move_line_date_against_its_move(env)
