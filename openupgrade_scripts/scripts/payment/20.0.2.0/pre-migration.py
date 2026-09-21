# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_rel = "payment_method_payment_provider_rel"
_legacy_rel = openupgrade.get_legacy_name(_rel)


@openupgrade.migrate()
def migrate(env, version):
    # payment.method.provider_ids was a many2many in 19.0 and is gone in 20.0,
    # replaced by the provider_id many2one. Its relation table is the only record
    # of which provider supported which method, and end-migration needs it to
    # give each company's provider its methods back.
    #
    # Keeping the table under its own name is not enough: its foreign keys
    # cascade, so deleting the obsolete provider-agnostic methods would empty it.
    # Dropping the keys and renaming leaves an inert copy of the 19.0 state,
    # which is what OpenUpgrade keeps legacy data for.
    if not openupgrade.table_exists(env.cr, _rel) or openupgrade.table_exists(
        env.cr, _legacy_rel
    ):
        return
    env.cr.execute(
        """
        SELECT conname FROM pg_constraint
        WHERE conrelid = %s::regclass AND contype IN ('f', 'p')
        """,
        (_rel,),
    )
    for (conname,) in env.cr.fetchall():
        openupgrade.logged_query(
            env.cr, f'ALTER TABLE {_rel} DROP CONSTRAINT "{conname}"'
        )
    # Not openupgrade.rename_tables: it renames the constraints along with the
    # table, and both foreign key names prefixed with the legacy name truncate to
    # the same 63 character identifier, so the second rename collides with the
    # first. A plain rename leaves the indexes named after the old table, which
    # is cosmetic on a table nothing queries by name any more.
    openupgrade.logged_query(env.cr, f"ALTER TABLE {_rel} RENAME TO {_legacy_rel}")
