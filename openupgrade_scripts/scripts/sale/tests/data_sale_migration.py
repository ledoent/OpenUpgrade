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

env.cr.commit()
