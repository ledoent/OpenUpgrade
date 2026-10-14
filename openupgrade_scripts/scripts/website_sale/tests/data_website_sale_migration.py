env = locals().get("env")

# 19.0 attached an extra product image to one variant through
# product.image.product_variant_id. 20.0 attaches every image to the template
# and works out which variants it is for from attribute_value_ids, so an image
# carrying neither belongs to nothing and disappears from the shop.
#
# Three shapes have to be told apart, and the seed contains all three, so they
# are marked rather than built: building a variant means building a template,
# its attribute lines and its combinations, which would test the fixture rather
# than the migration.
variants = env["product.product"].with_context(active_test=False)
images = env["product.image"].with_context(active_test=False)
candidates = images.search([("product_variant_id", "!=", False)], order="id")
assert candidates, "the seed needs extra images attached to variants"

marked = {}
for image in candidates:
    variant = image.product_variant_id
    siblings = variants.search_count(
        [("product_tmpl_id", "=", variant.product_tmpl_id.id)]
    )
    if variant.product_template_attribute_value_ids:
        shape = "combination"  # keeps the template and the attribute values
    elif siblings == 1:
        shape = "only-variant"  # the template alone says what 19.0 said
    else:
        shape = "orphan"  # an obsolete combination, with nothing to attach to
    if shape not in marked:
        image.name = f"ou19-image-{shape}"
        marked[shape] = image.id

# All three, loudly. A shape the fixture cannot find is one the test would then
# skip, and a skipped assertion reports success for a migration nobody checked.
for shape in ("combination", "only-variant", "orphan"):
    assert shape in marked, f"the seed has no {shape} variant image to mark"

# --- the contact-us url that a default would overwrite -----------------------
# contact_us_button_url -> contact_us_link_url. Both declare
# default="/contactus", so the new column is created already holding it and a
# site pointing elsewhere loses its own value in silence. A value that is NOT
# "/contactus" is the only one that can tell a rename from a default.
websites = env["website"].search([], order="id")
assert len(websites) >= 2, "the seed needs two websites to tell them apart"
websites[0].contact_us_button_url = "/ou19-contact-somewhere-else"

# --- the three category display flags ----------------------------------------
# 19.0 kept them per category; 20.0 keeps them per website. Every category is
# first set to say show_category_description = FALSE, which is NOT the 19.0
# default and not 20.0's website default either -- so a website that ends up
# False can only have got there by being carried.
#
# Then one category belonging to the FIRST website alone says True. A website's
# categories are its own plus the global ones, so that website's set now
# disagrees and must be reported rather than resolved, while the second website
# sees only the global ones, agrees, and is carried.
env.cr.execute("UPDATE product_public_category SET show_category_description = false")
env["product.public.category"].create(
    {
        "name": "ou19-category-global-says-no-description",
        "show_category_description": False,
    }
)
env["product.public.category"].create(
    {
        "name": "ou19-category-disagreeing",
        "website_id": websites[0].id,
        "show_category_description": True,
    }
)
for record, name in ((websites[0], "ou19_website_disagreeing"),
                     (websites[1], "ou19_website_agreeing")):
    env["ir.model.data"].create(
        {
            "module": "__ou19__",
            "name": name,
            "model": "website",
            "res_id": record.id,
        }
    )

# --- the reference price that a group used to gate ---------------------------
# 19.0 showed the $/kg price whenever the feature group was enabled, with no
# per-website dimension; 20.0 also requires website.show_product_reference_price,
# which starts False. Enabling the group is how 19.0 expressed "on", so this is
# the state an upgraded shop actually arrives in.
env.ref("base.group_user").write(
    {"implied_ids": [(4, env.ref("website_sale.group_show_uom_price").id)]}
)

env.cr.commit()
