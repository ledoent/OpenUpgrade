env = locals().get("env")

# 19.0 asked whether extra hours needed a manager's approval through
# res.company.attendance_overtime_validation. 20.0 asks the same question as
# attendance_validation, a different column, which therefore takes its own
# default -- so by_manager is not carried and the company silently starts
# approving extra hours automatically.
#
# Every one of the seed's 117 companies is on no_validation, which is also the
# 20.0 default, so the seed agrees with the broken behaviour and the fix would
# be asserted by a database that cannot disagree. by_manager has to be planted.
company = env["res.company"].search([], order="id", limit=1)
assert company, "the seed needs a company"
company.attendance_overtime_validation = "by_manager"

# One, deliberately: the test asserts the others were left alone, which is what
# says the carry wrote only where 19.0 had an answer to carry.
others = env["res.company"].search_count(
    [("id", "!=", company.id), ("attendance_overtime_validation", "=", "by_manager")]
)
assert not others, "another company is already on by_manager"

env.cr.commit()
