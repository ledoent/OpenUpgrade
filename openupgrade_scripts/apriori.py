"""Encode any known changes to the database here
to help the matching process
"""

# Renamed modules is a mapping from old module name to new module name
renamed_modules = {
    # odoo
    # the feature outgrew website_sale and is now usable outside the shop
    "website_sale_autocomplete": "website_address_autocomplete",
    # purchase_requisition_sale -> purchase_alternative_sale looks right by name
    # but is not: treating it as a rename leaves the upgrade building a foreign
    # key on purchase_alternative_warning_id, a column nothing creates. Left out
    # until someone works out what actually became of it.
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
    # absorbed modules with no field of their own left to trace, matched to the
    # module that carries their feature in 20.0 and confirmed to exist there
    "base_iban": "base",
    "hr_holidays_homeworking": "hr_holidays",
    "hr_homeworking_calendar": "hr",
    "hr_work_entry_holidays": "hr_work_entry",
    "iot_base": "iot_drivers",
    "l10n_cn_city": "l10n_cn",
    "l10n_dk_oioubl": "l10n_dk",
    "l10n_ec_stock": "l10n_ec",
    "l10n_fr_hr_work_entry_holidays": "l10n_fr_hr_holidays",
    "l10n_latam_base": "l10n_latam_invoice_document",
    "l10n_sa_withholding_tax": "l10n_sa",
    "l10n_tr_nilvera": "l10n_tr",
    "l10n_tr_nilvera_base_vat": "l10n_tr",
    "l10n_tr_nilvera_edispatch": "l10n_tr",
    "l10n_tr_nilvera_einvoice": "l10n_tr",
    "l10n_uy_pos": "l10n_uy",
    "mrp_subcontracting_repair": "mrp_subcontracting",
    "pos_restaurant_stripe": "pos_stripe",
    "pos_self_order_adyen": "pos_adyen",
    "pos_self_order_stripe": "pos_stripe",
    "website_sale_collect_wishlist": "website_sale",
    "website_sale_comparison_wishlist": "website_sale",
    "website_sale_stock_wishlist": "website_sale_stock",
    # delivery_mondialrelay, website_sale_mondialrelay and transifex are simply
    # gone in 20.0 with nothing carrying them, so there is nothing to merge into
    # odoo/enterprise
    # OCA/...
}

# Renamed models is a mapping from old model name to new model name
renamed_models = {
    # odoo
    # the valuation report moved from stock_account into account
    "stock_account.stock.valuation.report": "account.stock.valuation.report",
    "hr.contract.type": "hr.employee.type",
    "l10n_tr_nilvera_einvoice_extended.tax.office": "l10n_tr.tax.office",
    # OCA/...
}

# only used here for upgrade_analysis
merged_models = {
    # odoo
    # OCA/...
}
