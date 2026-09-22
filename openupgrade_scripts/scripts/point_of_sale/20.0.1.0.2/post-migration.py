# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _fill_payment_method_type(env):
    """pos.payment.method.type was computed in 19.0 and is stored in 20.0.

    19.0 derived it on the fly and kept no column, so the stored column 20.0
    adds starts empty against a required field -- the upgrade reports
    "Constraint not added: column type of relation pos_payment_method contains
    null values" and carries on without the constraint.

    The rule is 19.0's own _compute_type, which reads the journal rather than
    anything on the method itself::

        if pm.journal_id.type in {'cash', 'bank'}:
            pm.type = pm.journal_id.type
        else:
            pm.type = 'pay_later'

    A method with no journal falls to pay_later, which is why the join is outer.
    Not is_cash_count: that agrees with the journal on a cash method but is a
    different field, and 20.0 drops it.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE pos_payment_method m
        SET type = CASE
            WHEN j.type IN ('cash', 'bank') THEN j.type
            ELSE 'pay_later'
        END
        FROM pos_payment_method m2
        LEFT JOIN account_journal j ON j.id = m2.journal_id
        WHERE m.id = m2.id AND m.type IS NULL
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "point_of_sale", "20.0.1.0.2/noupdate_changes.xml")
    _fill_payment_method_type(env)
