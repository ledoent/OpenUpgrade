# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """19.0 split TDS by direction; 20.0 has a single key.

    account.tax.l10n_in_tax_type offered tds_sale and tds_purchase in 19.0 and
    offers tds in 20.0. A selection is enforced in Python rather than by the
    database, so the rows keep the old key silently: they read as blank in the
    interface and match neither branch of a domain over the field. 258 of the
    seed's taxes.

    Nothing is lost by folding them together. Which direction a tax applies to
    is what type_tax_use records, and it is untouched here.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE account_tax SET l10n_in_tax_type = 'tds'
        WHERE l10n_in_tax_type IN ('tds_sale', 'tds_purchase')
        """,
    )
