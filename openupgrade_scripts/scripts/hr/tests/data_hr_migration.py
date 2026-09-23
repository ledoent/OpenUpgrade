env = locals().get("env")

# hr.contract.type became hr.employee.type, and the fields pointing at it were
# renamed with it: hr.version.contract_type_id and hr.job.contract_type_id both
# became employee_type_id. Because the comodel was renamed in the same release
# the pair reads as pointing at a different model, which is how a rename gets
# annotated as a new field and 20 versions and 7 jobs come out with none.
#
# Existing records are marked rather than created: a version carries a wage, a
# schedule and a responsible, and hr.job feeds recruitment, so a synthetic one
# would be testing the fixture.
versions = env["hr.version"].with_context(active_test=False)

with_type = versions.search([("contract_type_id", "!=", False)], order="id", limit=1)
assert with_type, "the seed needs a version with a contract type"
with_type.name = "ou19-version-contract-type"

job = env["hr.job"].search([("contract_type_id", "!=", False)], order="id", limit=1)
assert job, "the seed needs a job with a contract type"
job.name = "ou19-job-contract-type"

# 19.0's employee_type classified the person and 20.0 drops it. Every version on
# the seed is on the default, so the one value worth reporting -- a chosen one --
# does not occur naturally and has to be planted, or the report is asserted by a
# database that cannot produce it.
other = versions.search(
    [("id", "!=", with_type.id), ("employee_type", "=", "employee")],
    order="id",
    limit=1,
)
assert other, "the seed needs a second version"
other.name = "ou19-version-student"
env.cr.execute(
    "UPDATE hr_version SET employee_type = 'student' WHERE id = %s", (other.id,)
)

env.cr.commit()
