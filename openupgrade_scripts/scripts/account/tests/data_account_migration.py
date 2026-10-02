env = locals().get("env")

# 19.0's `checked` ("Reviewed") becomes 20.0's review_state, and only a posted
# move whose checked is FALSE carries information: 19.0's compute would have set
# it True, so a False there was put there by hand.
#
# This seed contains no such row -- `checked` equals `state = 'posted'` on all
# 3223 of its moves -- so the branch that writes 'todo' is unreachable without
# this, and a test over the seed alone would pass against a migration that does
# nothing at all.
#
# An existing move is unticked rather than a new one built: posting a journal
# entry from a shell needs a journal, balanced lines and an open period, none of
# which is what is under test, and each of which is a way for the fixture to
# fail for its own reasons.
move = env["account.move"].search([("state", "=", "posted")], order="id", limit=1)
assert move, "the seed has no posted move to untick"

# Written straight to the column. `checked` is a stored compute in 19.0, so
# assigning it through the ORM invites the compute to put it back; and the field
# does not exist in 20.0, so nothing recomputes it during the upgrade either.
env.cr.execute("UPDATE account_move SET checked = false WHERE id = %s", (move.id,))

# A second, untouched posted move, so the test can say the rule discriminates
# rather than sweeping every posted entry into the review queue.
other = env["account.move"].search(
    [("state", "=", "posted"), ("id", "!=", move.id)], order="id", limit=1
)
assert other, "the seed has only one posted move, so nothing can be left alone"

for record, name in (
    (move, "ou19_move_unreviewed_by_hand"),
    (other, "ou19_move_left_alone"),
):
    env["ir.model.data"].create(
        {
            "module": "__ou19__",
            "name": name,
            "model": "account.move",
            "res_id": record.id,
        }
    )

# --- the deductibility scale change ------------------------------------------
# 19.0's deductible_amount is a 0-100 percentage; 20.0's deductible_percentage
# is a 0-1 fraction. The two defaults -- 100 and 1.0 -- mean the same thing, so
# a line left on the default proves nothing either way. 50 is planted because it
# is the one value that comes out wrong: without the rescale the line reads as
# fully deductible and 20.0 claims the whole VAT on a half-private expense.
#
# It must sit on a vendor bill: 20.0 forbids deductibility anywhere else
# ("Only vendor bills allow for deductibility of product/services.",
# account_move_line.py:1971), so a sales line could not hold the value at all.
bill_line = env["account.move.line"].search(
    [
        ("move_id.move_type", "in", ("in_invoice", "in_refund", "in_receipt")),
        ("display_type", "=", "product"),
    ],
    order="id",
    limit=1,
)
assert bill_line, "the seed has no vendor bill product line to mark part-deductible"
env.cr.execute(
    "UPDATE account_move_line SET deductible_amount = 50 WHERE id = %s",
    (bill_line.id,),
)
env["ir.model.data"].create(
    {
        "module": "__ou19__",
        "name": "ou19_line_half_deductible",
        "model": "account.move.line",
        "res_id": bill_line.id,
    }
)

env.cr.commit()
