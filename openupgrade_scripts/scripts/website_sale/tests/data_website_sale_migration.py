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

env.cr.commit()
