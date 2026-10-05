# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


_renamed_fields = [
    # Same field, new name, same default. 19.0's contact_us_button_url and
    # 20.0's contact_us_link_url are both Char(translate=True,
    # default="/contactus"), the latter read by _get_contact_us_url(). Because
    # the new column is created WITH that default, a site pointing its button at
    # /help or an external form silently gets "/contactus" back while its own
    # value sits in the column 20.0 no longer reads. Renaming carries the jsonb
    # translations too, which both versions store.
    (
        "website",
        "website",
        "contact_us_button_url",
        "contact_us_link_url",
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_fields(env, _renamed_fields)
    # The three category display flags move from product.public.category to
    # website, so these columns are the only record of what each category was
    # set to. Renamed rather than read in place because 20.0 declares nothing of
    # the sort on the category -- post-migration aggregates them per website.
    category_flags = [
        flag
        for flag in (
            "show_category_title",
            "show_category_description",
            "align_category_content",
        )
        if openupgrade.column_exists(env.cr, "product_public_category", flag)
    ]
    if category_flags:
        openupgrade.rename_columns(
            env.cr,
            {"product_public_category": [(flag, None) for flag in category_flags]},
        )
    # 19.0 hung an extra product image off one variant through
    # product.image.product_variant_id. 20.0 hangs every image off the template
    # and says which variants it belongs to through attribute_value_ids, so the
    # old column is the only record of which variant an image was for.
    # post-migration reads it back.
    if openupgrade.column_exists(env.cr, "product_image", "product_variant_id"):
        openupgrade.rename_columns(
            env.cr, {"product_image": [("product_variant_id", None)]}
        )
