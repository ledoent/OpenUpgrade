# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Helpers shared between migration scripts.

Import from a script with

    # pylint: disable=odoo-addons-relative-import
    from odoo.addons.openupgrade_scripts.helpers import release_xmlid
"""

from openupgradelib import openupgrade


def release_xmlid(cr, xmlid, model):
    """Free an external id that 20.0 re-ships against a different model.

    The loader refuses to bind an external id to a record whose model is not
    the one the data file declares, so an id that changes model between
    versions has to be released first. Several actions do: 19.0 shipped them
    as ir.actions.act_window and 20.0 ships the same ids as
    ir.actions.server.

    Only the ir_model_data row goes. The record it pointed at is left where it
    is, the way OpenUpgrade leaves residual data for database_cleanup rather
    than deleting it during an upgrade.

    openupgradelib has nothing for this. delete_records_safely_by_xml_id
    removes the record itself and needs the model in the registry, which is
    wrong for a pre-migration step.

    :param xmlid: full external id, "module.name".
    :param model: the model the id currently points at, so that an id already
        re-pointed by an earlier run is left alone.
    """
    module, _, name = xmlid.partition(".")
    openupgrade.logged_query(
        cr,
        """
        DELETE FROM ir_model_data
        WHERE module = %s AND name = %s AND model = %s
        """,
        (module, name, model),
    )
