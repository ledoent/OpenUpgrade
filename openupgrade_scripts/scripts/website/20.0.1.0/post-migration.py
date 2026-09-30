# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# 20.0 moved _get_visitor_from_request from website.visitor to ir.http
# (website/models/ir_http.py:449; website/data/website_data.xml now calls it as
# env['ir.http']._get_visitor_from_request()).
#
# The module update rewrites the views it owns, so website.contactus comes
# through correct. It cannot rewrite a COW copy: when a page is edited, Odoo
# duplicates the view with website_id set and NO ir_model_data row, and a
# record no xmlid points at is invisible to every module update thereafter. The
# copy keeps the 19.0 call, and since it is the one actually served for that
# website, /contactus answers 500 with
#   AttributeError: 'website.visitor' object has no attribute
#   '_get_visitor_from_request'
#
# Measured on a 19.0 production copy: one COW view out of eleven carried the
# call, and the public Contact Us page was down. The OCA seed has no COW views
# at all, which is why only real data could show this.
#
# Matched on the subscript rather than the whole call so both spellings in the
# wild are covered -- env[...] and request.env[...].
MOVED_TO_IR_HTTP = [
    (
        "['website.visitor']._get_visitor_from_request",
        "['ir.http']._get_visitor_from_request",
    ),
    (
        '["website.visitor"]._get_visitor_from_request',
        '["ir.http"]._get_visitor_from_request',
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "website", "20.0.1.0/noupdate_changes.xml")

    for old, new in MOVED_TO_IR_HTTP:
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE ir_ui_view
            SET arch_db = replace(arch_db::text, %(old)s, %(new)s)::jsonb
            WHERE arch_db::text LIKE %(like)s
            """,
            {"old": old, "new": new, "like": f"%{old}%"},
        )
