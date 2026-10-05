# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# pylint: disable=odoo-addons-relative-import
from odoo.addons.openupgrade_scripts.helpers import release_xmlid


@openupgrade.migrate()
def migrate(env, version):
    # 19.0 shipped the list merge action as an ir.actions.act_window opening
    # the merge wizard; 20.0 ships the same external id as an
    # ir.actions.server.
    release_xmlid(
        env.cr, "mass_mailing.mailing_list_merge_action", "ir.actions.act_window"
    )
