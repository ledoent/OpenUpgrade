env = locals().get("env")

# website.menu.url stops being stored in 20.0 and becomes a compute that reads
# website.page for a page-backed menu and `manual_url` for a hand-typed one. A
# menu with neither falls through to "#", so the link stays in the navigation
# bar and goes nowhere.
#
# The seed already carries 48 such menus, so the branch is reachable without
# this -- but every one of them holds a URL the fixture did not choose, which
# makes an assertion about a specific value impossible. A menu with a distinctive
# address is planted so the test can say exactly what should have survived.
#
# No page_id on purpose: a page-backed menu is the case that works without any
# migration at all, and asserting on it would pass against a script that does
# nothing.
parent = env["website.menu"].search([("parent_id", "=", False)], order="id", limit=1)
assert parent, "the seed needs at least one root website menu"

env["website.menu"].create(
    {
        "name": "ou19-hand-typed-menu",
        "url": "/ou19-typed-by-hand",
        "parent_id": parent.id,
        "website_id": parent.website_id.id,
    }
)

# A second one holding '#'. The compute returns "#" for a mega menu or a menu
# with children whatever manual_url says, so carrying it would add a row that
# changes nothing a visitor sees -- this proves the script leaves it alone.
env["website.menu"].create(
    {
        "name": "ou19-hash-menu",
        "url": "#",
        "parent_id": parent.id,
        "website_id": parent.website_id.id,
    }
)

env.cr.commit()
