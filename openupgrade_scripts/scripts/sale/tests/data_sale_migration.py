env = locals().get("env")

# product.template.sale_delay moves from stock to sale and becomes
# company_dependent, which in 20.0 means jsonb on the table rather than an
# ir.property row. Postgres cannot cast the integer column to jsonb, so
# pre-migration parks the values under a legacy name and post-migration puts
# them back keyed by company.
#
# A non-zero delay is the whole point: zero is the field default, so a product
# left at zero would pass whether or not anything carried the value across.
product = env["product.template"].create(
    {
        "name": "ou19-sale-delay-product",
        "sale_delay": 7,
    }
)

# A second product left at the default, to show the migration does not write
# rows for values that were never set.
env["product.template"].create({"name": "ou19-sale-delay-default"})

assert product.sale_delay == 7

# --- the two policy settings that become company fields -----------------------
# 19.0 kept both as ir.default rows; 20.0 adds res.company.sale_invoice_policy
# (default "order") and res.company.picking_policy (default "direct"). The prod
# copy holds exactly those two defaults, so the carry is invisible there -- the
# values planted here are the OPPOSITE ones, which is the only arrangement that
# can tell a carry from a default.
env["ir.default"].set("product.template", "invoice_policy", "delivery")
env["ir.default"].set("sale.order", "picking_policy", "one")

env.cr.commit()
