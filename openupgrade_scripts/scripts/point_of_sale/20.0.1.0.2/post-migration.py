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


def _swap_the_two_journals_back_into_their_20_meanings(env):
    """pos.config's two journals changed jobs, and the precompute invented one.

    19.0 held them the other way round. `journal_id` was the SESSION CLOSING
    journal -- _create_account_move posted the closing entry to
    `self.config_id.journal_id` (19.0 pos_session.py:819) -- and
    `invoice_journal_id` was the journal for POS invoices
    (19.0 pos_order.py:919). The settings page labelled the two rows "Orders"
    and "Invoices".

    20.0 swaps them. _prepare_invoice_vals now reads `config_id.journal_id`
    (pos_order.py:1557), and the closing entry goes to the new
    `closing_journal_id` (pos_session.py:988). Nothing moved the values, so
    after the upgrade both are wrong at once:

      * POS invoices are cut from the old CLOSING journal. Measured on a 19->20
        run over the sanitised prod copy 2026-10-02: that journal is POSS, which
        holds 0 moves of any kind, while INV -- the journal still named by
        invoice_journal_id -- holds 508. So the unfixed upgrade cuts invoices
        into a journal with no history while the one actually used for
        invoicing goes unreferenced. (The copy carries no pos.order rows, so the
        argument rests on which journal is which, not on a count of POS
        invoices.)
      * closing_journal_id was filled by _compute_closing_journal_id, which
        calls _ensure_company_closing_journal() and CREATES a POSC journal. The
        copy ends up pointing at a journal whose create_date is the migration
        run itself -- a journal invented by the upgrade, not chosen by anyone.

    So this is a swap, written in one statement because each half reads the
    column the other half overwrites.

    The closing side is guarded. 19.0's journal_id allowed ('general', 'sale')
    and 20.0's closing_journal_id allows ('sale',) alone, so a config that
    closed into a general journal has no legal home in 20.0; those keep
    whatever _ensure_company_closing_journal gave them and are reported, which
    is better than writing a value the form would reject.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE pos_config c
        SET journal_id = c.invoice_journal_id,
            closing_journal_id = CASE
                WHEN j.type = 'sale' THEN c.journal_id
                ELSE c.closing_journal_id
            END
        FROM account_journal j
        WHERE j.id = c.journal_id
          AND c.invoice_journal_id IS NOT NULL
        """,
    )
    swapped = env.cr.rowcount
    if swapped:
        openupgrade.message(
            env.cr,
            "point_of_sale",
            False,
            False,
            "pos.config: moved the invoice journal of %s config(s) into "
            "journal_id, which is what 20.0 cuts POS invoices from, and their "
            "19.0 closing journal into closing_journal_id; left alone, invoices "
            "would have been posted to the closing journal",
            swapped,
        )
    env.cr.execute(
        """
        SELECT count(*)
        FROM pos_config c
        JOIN account_journal j ON j.id = c.closing_journal_id
        WHERE j.type != 'sale'
        """
    )
    not_sale = env.cr.fetchone()[0]
    if not_sale:
        openupgrade.message(
            env.cr,
            "point_of_sale",
            False,
            False,
            "pos.config: %s config(s) closed into a journal 20.0 will not accept "
            "there -- its closing_journal_id takes a sale journal where 19.0 also "
            "allowed a general one -- so they keep the journal 20.0 created for "
            "them and should be pointed at the right one by hand",
            not_sale,
        )


def _keep_posting_session_accounting_on_close(env):
    """20.0's 'daily' default starts posting entries nobody asked it to.

    19.0 built the session's accounting entry when somebody CLOSED the session,
    and shipped no cron to do it otherwise -- point_of_sale/data holds no
    ir.cron record for it at all.

    20.0 adds session_closing_mode, defaults it to 'daily', and ships
    point_of_sale.ir_cron_pos_auto_order_invoicing active, every 10 minutes.
    Its _launch_cron_generate_invoice_period selects
    ('config_id.session_closing_mode', '=', 'daily') and calls
    _validate_session_accounting on sessions that are still OPEN. So an
    upgraded database quietly starts posting session accounting at
    session_closing_daily_hour -- 04:00 on the prod copy -- whether or not
    anyone closed the session.

    'closing' is 20.0's spelling of what 19.0 did, so that is what a
    pre-existing config gets. A database upgraded and then deliberately moved
    to daily is unaffected: this runs once, during the upgrade.

    The lab disables every cron wholesale, so no seed can show the effect --
    the evidence is 20.0's own data file and the cron's domain.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE pos_config
        SET session_closing_mode = 'closing'
        WHERE session_closing_mode = 'daily'
        """,
    )
    if env.cr.rowcount:
        openupgrade.message(
            env.cr,
            "point_of_sale",
            False,
            False,
            "pos.config: %s config(s) were put on 20.0's 'closing' session mode, "
            "which is what 19.0 did; the 'daily' default would have had a cron "
            "post their session accounting unattended",
            env.cr.rowcount,
        )


def _carry_the_payment_currency_rate_now_that_it_is_stored(env):
    """pos.payment.currency_rate stopped being related and started being stored.

    19.0 declared it `related='pos_order_id.currency_rate'` with no store, so
    there was no column and every read went through to the order. 20.0 declares
    a plain stored Float (pos_payment.py:39) and nothing fills it for rows that
    already exist, so historical payments read 0.

    The source is intact: pos.order.currency_rate is a stored compute in both
    versions and its column survives the upgrade untouched, so copying it
    across reproduces exactly what 19.0 returned.

    pos_payment holds 0 rows on the sanitised prod copy, so the migration test
    is what exercises this.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE pos_payment p
        SET currency_rate = o.currency_rate
        FROM pos_order o
        WHERE o.id = p.pos_order_id
          AND o.currency_rate IS NOT NULL
          AND (p.currency_rate IS NULL OR p.currency_rate = 0)
        """,
    )
    if env.cr.rowcount:
        openupgrade.message(
            env.cr,
            "point_of_sale",
            False,
            False,
            "pos.payment: carried the order's currency rate onto %s payment(s); "
            "19.0 read it through a related field that 20.0 stores instead",
            env.cr.rowcount,
        )


def _relink_the_session_closing_move(env):
    """19.0's pos.session.move_id becomes a column on the move itself.

    19.0 kept the session's closing entry as one many2one on the session
    (19.0 pos_session.py:88). 20.0 inverts the link and splits it three ways on
    account.move -- pos_session_sales_id, pos_session_refunds_id and
    pos_session_correction_id -- surfaced as sale_move_ids / refund_move_ids /
    correction_move_ids. Nothing filled them; the analysis records all three as
    empty on every row, while the old move_id column survives with its foreign
    key intact.

    Sales is the right home: 19.0 posted sales and refunds into one move.

    Not cosmetic. 20.0's _compute_always_tax_exigible keys off pos_session_ids
    and forces always_tax_exigible True for a move that belongs to a session,
    with a source comment anticipating exactly these rows ("there may still be
    old closing moves that used caba entries from previous versions"), so an
    unlinked historical closing move can recompute to the wrong exigibility.
    """
    if not openupgrade.column_exists(env.cr, "pos_session", "move_id"):
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE account_move m
        SET pos_session_sales_id = s.id
        FROM pos_session s
        WHERE s.move_id = m.id
          AND m.pos_session_sales_id IS NULL
        """,
    )
    if env.cr.rowcount:
        openupgrade.message(
            env.cr,
            "point_of_sale",
            False,
            False,
            "account.move: re-pointed %s session closing move(s) at their "
            "session through 20.0's pos_session_sales_id; the link drives "
            "_compute_always_tax_exigible",
            env.cr.rowcount,
        )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "point_of_sale", "20.0.1.0.2/noupdate_changes.xml")
    _fill_payment_method_type(env)
    _swap_the_two_journals_back_into_their_20_meanings(env)
    _keep_posting_session_accounting_on_close(env)
    _carry_the_payment_currency_rate_now_that_it_is_stored(env)
    _relink_the_session_closing_move(env)
