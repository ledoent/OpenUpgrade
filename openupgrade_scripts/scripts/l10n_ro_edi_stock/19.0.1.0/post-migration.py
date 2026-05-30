# Copyright 2026 Ledoent
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE l10n_ro_edi_document
        SET state = 'invoice_refused'
        WHERE state = 'invoice_sending_failed'
        """,
    )
