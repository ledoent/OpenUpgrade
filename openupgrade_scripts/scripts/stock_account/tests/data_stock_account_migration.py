env = locals().get("env")

# A FIFO receipt carrying TWO valuation layers (base + an adjustment, the
# landed-cost shape) and a partial FIFO delivery (negative layer). The
# post-migration test asserts the layers collapse to one product.value row
# per move and that the outbound value migrates as a magnitude.
categ = env["product.category"].create(
    {"name": "OU SVL agg test", "property_cost_method": "fifo"}
)
product = env["product.product"].create(
    {
        "name": "OU SVL agg part",
        "type": "consu",
        "is_storable": True,
        "categ_id": categ.id,
    }
)
Move = env["stock.move"]
in_move = Move.create(
    {
        "name": "OU test receipt",
        "product_id": product.id,
        "product_uom_qty": 10,
        "product_uom": product.uom_id.id,
        "location_id": env.ref("stock.stock_location_suppliers").id,
        "location_dest_id": env.ref("stock.stock_location_stock").id,
        "price_unit": 100.0,
    }
)
in_move._action_confirm()
in_move.quantity = 10
in_move.picked = True
in_move._action_done()
# second layer on the same move: the landed-cost/adjustment shape
env["stock.valuation.layer"].create(
    {
        "product_id": product.id,
        "quantity": 0,
        "value": 50.0,
        "stock_move_id": in_move.id,
        "company_id": in_move.company_id.id,
        "description": "OU test adjustment",
    }
)
out_move = Move.create(
    {
        "name": "OU test delivery",
        "product_id": product.id,
        "product_uom_qty": 4,
        "product_uom": product.uom_id.id,
        "location_id": env.ref("stock.stock_location_stock").id,
        "location_dest_id": env.ref("stock.stock_location_customers").id,
    }
)
out_move._action_confirm()
out_move._action_assign()
out_move.quantity = 4
out_move.picked = True
out_move._action_done()
env["ir.model.data"].create(
    [
        {
            "module": "openupgrade_test",
            "name": "stock_account_in_move",
            "model": "stock.move",
            "res_id": in_move.id,
            "noupdate": True,
        },
        {
            "module": "openupgrade_test",
            "name": "stock_account_out_move",
            "model": "stock.move",
            "res_id": out_move.id,
            "noupdate": True,
        },
    ]
)
env.cr.commit()
