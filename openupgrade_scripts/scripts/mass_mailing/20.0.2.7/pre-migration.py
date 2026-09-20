# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _release_merge_action_xmlid(env):
    """The list merge action changed type, keeping its external id.

    19.0 shipped mass_mailing.mailing_list_merge_action as an
    ir.actions.act_window opening the merge wizard; 20.0 ships the same
    external id as an ir.actions.server. The loader refuses to bind an id to a
    record of a different model, so the id has to be released for 20.0's
    record to take it.

    Only the ir_model_data row goes. The orphaned window action is left where
    it is, the way OpenUpgrade leaves residual data for database_cleanup.
    """
    openupgrade.logged_query(
        env.cr,
        """
        DELETE FROM ir_model_data
        WHERE module = 'mass_mailing'
          AND name = 'mailing_list_merge_action'
          AND model = 'ir.actions.act_window'
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    _release_merge_action_xmlid(env)
