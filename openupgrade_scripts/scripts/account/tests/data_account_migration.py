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

env.cr.commit()
