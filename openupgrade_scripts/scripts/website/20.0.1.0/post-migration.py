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


def _carry_the_hand_typed_menu_url_into_manual_url(env):
    """website.menu.url stops being stored, and the hand-typed value has nowhere
    to be read from.

    19.0 stored the menu's URL in `url`. 20.0 makes that a non-stored compute and
    adds `manual_url` ("Url defined by user") as the place a hand-typed address
    actually lives::

        menu.url = (menu.page_id.url if menu.page_id else menu.manual_url) or "#"

    So a menu backed by a website.page is fine -- the compute reads the page. A
    menu whose address was typed in has nothing to read: `manual_url` arrives
    empty and the whole expression falls through to **"#"**. The link survives as
    an entry in the navigation bar and goes nowhere.

    Measured on the 585-module seed: 48 of 53 menus have neither a page nor a
    controller page, manual_url is empty on every one of the 53, and the
    orphaned `url` column still holds the values -- /blog, /event, / and so on.
    Unmigrated, that is every website's navigation turned into dead links.

    `#` is not carried: the compute already returns it for a mega menu or a menu
    with children regardless of manual_url, so writing it would add rows without
    changing what any visitor sees.

    The 19.0 column is read in place rather than renamed first. Nothing can
    overwrite it -- the field it belonged to is no longer stored, so the ORM
    neither reads nor writes that column.

    One menu is beyond reach, and it is core's rather than ours:
    `website.menu_home` is the template menu, carrying no website_id and no
    page, and 20.0's own data load puts it through _inverse_url, which writes
    `manual_url = ''` whenever the url it is handed is falsy. Its write_date is
    the upgrade itself, so anything written here is overwritten afterwards. It
    costs nothing: the live per-website Home menus are page-backed and resolve
    through website.page.
    """
    if not openupgrade.column_exists(env.cr, "website_menu", "url"):
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE website_menu
        SET manual_url = url
        WHERE page_id IS NULL
          AND controller_page_id IS NULL
          AND coalesce(manual_url, '') = ''
          AND url IS NOT NULL AND url NOT IN ('', '#')
        """,
    )
    if env.cr.rowcount:
        openupgrade.message(
            env.cr,
            "website",
            False,
            False,
            "website.menu: carried the hand-typed address of %s menu(s) into "
            "manual_url, which is where 20.0 reads it from; they would otherwise "
            "have computed to '#' and gone nowhere",
            env.cr.rowcount,
        )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "website", "20.0.1.0/noupdate_changes.xml")
    _carry_the_hand_typed_menu_url_into_manual_url(env)

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
