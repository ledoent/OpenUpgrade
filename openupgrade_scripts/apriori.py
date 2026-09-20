"""Encode any known changes to the database here
to help the matching process
"""

# Renamed modules is a mapping from old module name to new module name
renamed_modules = {
    # odoo
    # the feature outgrew website_sale and is now usable outside the shop
    "website_sale_autocomplete": "website_address_autocomplete",
    # odoo/enterprise
    # OCA/...
}

# Merged modules contain a mapping from old module names to other,
# preexisting module names
#
# Derived from the 19.0 -> 20.0 upgrade analysis: each entry below is a module
# that no longer exists in 20.0 and whose stored fields the analysis reports as
# "previously in module <old>" under exactly one new owner. Entries attributed
# only through res.partner.invoice_edi_format are deliberately absent -- that
# selection is contributed by every l10n EDI module, so its ownership says
# nothing about where a module went.
merged_modules = {
    # odoo
    "account_add_gln": "account",
    "account_peppol_response": "account_peppol",
    # partner VAT validation, every check_vat_* method, is now in base; only
    # res.company.vat_check_vies landed in account
    "base_vat": "base",
    "delivery_stock_picking_batch": "stock_delivery",
    "hr_homeworking": "hr",
    "hr_hourly_cost": "hr",
    "hr_org_chart": "hr",
    "l10n_dk_nemhandel": "l10n_dk",
    "l10n_dk_nemhandel_response": "l10n_dk",
    "l10n_pl_bank_verification": "l10n_pl",
    "l10n_ro_cpv_code": "l10n_ro_edi",
    "l10n_ro_edi_stock_batch": "l10n_ro_edi_stock",
    "l10n_tr_nilvera_einvoice_extended": "l10n_tr",
    "pos_restaurant_adyen": "pos_adyen",
    "stock_picking_batch": "stock",
    "website_sale_comparison": "website_sale",
    "website_sale_wishlist": "website_sale",
    # odoo/enterprise
    # OCA/...
}

# Renamed models is a mapping from old model name to new model name
renamed_models = {
    # odoo
    # OCA/...
}

# only used here for upgrade_analysis
merged_models = {
    # odoo
    # OCA/...
}
