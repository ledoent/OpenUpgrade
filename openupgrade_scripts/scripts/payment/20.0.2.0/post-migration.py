# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_legacy_state = openupgrade.get_legacy_name("state")


def _set_is_live(env):
    """Put the providers that were enabled in 19.0 into live mode.

    Only enabled. A test provider was already processing through the test
    interface, and a disabled one is not published, so False is right for both
    -- and it is what they have, is_live being new and defaulting to False.

    active is deliberately left alone. 19.0 had no such field, so setting it
    from state would archive every disabled provider and take it out of the
    backend list, where 19.0 showed it; disabled is carried by is_published,
    which 19.0 already had.
    """
    if not openupgrade.column_exists(env.cr, "payment_provider", _legacy_state):
        return
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE payment_provider
        SET is_live = TRUE
        WHERE {_legacy_state} = 'enabled'
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(
        env,
        "payment",
        "20.0.2.0/noupdate_changes.xml",
        xml_transformation_filename="20.0.2.0/noupdate_changes-transformation.xml",
    )
    _set_is_live(env)
