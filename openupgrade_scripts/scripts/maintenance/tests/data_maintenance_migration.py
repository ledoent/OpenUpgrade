env = locals().get("env")

# 19.0 records completion on the stage and assignment on a many2one; 20.0
# records the first on the request and the second on a many2many computed from
# the equipment. The seed can show neither: every one of its requests sits on a
# stage that is not done, and every one is assigned to exactly the technician
# its equipment carries, so the many2many comes out right whether anything
# carried it or not.
#
# The fixtures are filed under a module that does not exist. _process_end
# removes data rows belonging to modules it has just loaded, so an id claiming
# to be maintenance's would be deleted at the end of the run.
request_model = env["maintenance.request"]
stage_model = env["maintenance.stage"]

done_stage = stage_model.search([("done", "=", True)], limit=1)
open_stage = stage_model.search([("done", "=", False)], limit=1)
assert done_stage and open_stage, "the seed has no pair of stages to tell apart"

company = env.ref("base.main_company")
# Two different users, both in the request's company: the script applies 20.0's
# own company filter, so a technician outside it would be excluded by design and
# the test would be asserting the wrong thing.
users = env["res.users"].search(
    [("company_ids", "in", company.id), ("active", "=", True)], order="id", limit=2
)
assert len(users) == 2, "the seed has fewer than two users in the main company"
equipment_technician, other_technician = users[0], users[1]

equipment = env["maintenance.equipment"].create(
    {
        "name": "ou19-equipment",
        "company_id": company.id,
        "technician_user_id": equipment_technician.id,
    }
)

# 1. Finished in 19.0's terms: it sits in a stage marked done. 20.0 must read
#    it as done, or every count and every MTBF over it is computed as though the
#    maintenance had never been finished.
finished = request_model.create(
    {
        "name": "ou19-request-finished",
        "company_id": company.id,
        "equipment_id": equipment.id,
        "stage_id": done_stage.id,
        "user_id": equipment_technician.id,
    }
)

# 2. Not finished. This is the half that says the carry is targeted: a blanket
#    write would satisfy the assertion above and still be wrong.
open_request = request_model.create(
    {
        "name": "ou19-request-open",
        "company_id": company.id,
        "equipment_id": equipment.id,
        "stage_id": open_stage.id,
        "user_id": equipment_technician.id,
    }
)

# 3. Assigned to someone who is NOT the equipment's technician -- the row the
#    seed does not contain. 20.0's _compute_user_ids adds the equipment's
#    technician and nobody else, so without the carry this assignment is lost.
reassigned = request_model.create(
    {
        "name": "ou19-request-reassigned",
        "company_id": company.id,
        "equipment_id": equipment.id,
        "stage_id": open_stage.id,
        "user_id": other_technician.id,
    }
)

# 4. Blocked. 20.0 has no value that certainly means this, so the migration must
#    report it and leave state on its default rather than invent an answer.
blocked = request_model.create(
    {
        "name": "ou19-request-blocked",
        "company_id": company.id,
        "equipment_id": equipment.id,
        "stage_id": open_stage.id,
        "user_id": equipment_technician.id,
    }
)
blocked.write({"kanban_state": "blocked"})

for record, name in (
    (finished, "ou19_request_finished"),
    (open_request, "ou19_request_open"),
    (reassigned, "ou19_request_reassigned"),
    (blocked, "ou19_request_blocked"),
):
    env["ir.model.data"].create(
        {
            "module": "__ou19__",
            "name": name,
            "model": "maintenance.request",
            "res_id": record.id,
        }
    )

env.cr.commit()
