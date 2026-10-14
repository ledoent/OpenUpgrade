# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# pylint: disable=odoo-addons-relative-import
from odoo.addons.openupgrade_scripts.helpers import release_xmlid


def _rename_favorite_to_is_template(env):
    """`favorite` is renamed `is_template`, and the analysis cannot say so.

    The analysis reports the halves as unrelated lines -- `favorite` under DEL,
    `is_template` under NEW -- because a schema diff cannot see that they are one
    field. They are: 19.0's template fetcher reads

        domain = Domain('favorite', '=', True)

    and 20.0's `action_fetch_templates`, whose docstring is "Return all active
    mailings set as template", reads

        domain = Domain('is_template', '=', True)

    Same method, same job, new name. `favorite_date` has no 20.0 counterpart and
    is a genuine removal, so it is left alone.

    This was annotated NOTHING TO DO on the strength of a two-row sample in which
    `favorite` happened to be false everywhere -- true of that database, not of
    the field. A production copy with 35 mailings, one of them favourited, is
    what exposed it: the row came out of the migration with `favorite` still true
    and `is_template` false, so a mailing the customer had marked as a template
    silently stopped being one.
    """
    if not openupgrade.column_exists(env.cr, "mailing_mailing", "favorite"):
        return
    openupgrade.rename_fields(
        env,
        [
            (
                "mailing.mailing",
                "mailing_mailing",
                "favorite",
                "is_template",
            )
        ],
    )


@openupgrade.migrate()
def migrate(env, version):
    # 19.0 shipped the list merge action as an ir.actions.act_window opening
    # the merge wizard; 20.0 ships the same external id as an
    # ir.actions.server.
    release_xmlid(
        env.cr, "mass_mailing.mailing_list_merge_action", "ir.actions.act_window"
    )
    _rename_favorite_to_is_template(env)
