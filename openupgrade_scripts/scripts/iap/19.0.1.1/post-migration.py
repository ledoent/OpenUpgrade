# Copyright 2026 Ledo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # the legacy prefix (openupgrade_legacy_<N>_0_*) depends on the DB's history
    env.cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'iap_account'
           AND column_name LIKE 'openupgrade_legacy_%_service_name'
         ORDER BY column_name
         LIMIT 1
        """
    )
    row = env.cr.fetchone()
    if not row:
        return
    legacy_col = row[0]
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE iap_account a
        SET service_id = s.id
        FROM iap_service s
        WHERE a.service_id IS NULL
          AND a.{legacy_col} = s.technical_name
        """,
    )
