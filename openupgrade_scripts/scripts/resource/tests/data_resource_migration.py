env = locals().get("env")

# duration_hours is computed and not stored in 19.0; 20.0 stores it and adds
# CHECK(duration_hours > 0 AND duration_hours <= 24), so the column the upgrade
# creates starts at zero and has to be derived from the span.
#
# On a calendar of its own, with no other attendance on that day. 20.0 validates
# a calendar's attendances against each other -- overlapping spans are refused
# -- so hanging a fixture off an existing calendar tests the fixture's luck
# rather than the migration.
calendar = env["resource.calendar"].create({"name": "ou19-calendar"})
calendar.attendance_ids.unlink()
env["resource.calendar.attendance"].create(
    {
        "name": "ou19-attendance-span",
        "calendar_id": calendar.id,
        "dayofweek": "0",
        "hour_from": 8.0,
        "hour_to": 12.0,
    }
)

# There is deliberately no equal-hours attendance. 20.0 refuses to write one --
# its attendance validation rejects a zero-length span outright -- so such a row
# cannot be planted here, and a 19.0 database carrying one would fail the
# upgrade on that constraint rather than on the backfill. The backfill's guard
# against inventing a duration for it is covered by the reporting path instead.

# 19.0's schedule_type becomes 20.0's calendar_type, and the three answers below
# are the three the mapping has to tell apart. The seed cannot: 122 of its 124
# calendars are fully_fixed, exactly one is flexible, and NONE is in two-weeks
# mode -- so the branch that produces 'variable' is unreachable without this.
schedule_flexible = env["resource.calendar"].create(
    {"name": "ou19-calendar-flexible", "schedule_type": "flexible"}
)
schedule_two_weeks = env["resource.calendar"].create(
    {"name": "ou19-calendar-two-weeks", "two_weeks_calendar": True}
)
schedule_fully_fixed = env["resource.calendar"].create(
    {"name": "ou19-calendar-fully-fixed", "schedule_type": "fully_fixed"}
)
# Named ids rather than a search on name: a calendar's name is translatable in
# 20.0, and searching a jsonb column by its English value is not the same query.
for record, name in (
    (schedule_flexible, "ou19_calendar_flexible"),
    (schedule_two_weeks, "ou19_calendar_two_weeks"),
    (schedule_fully_fixed, "ou19_calendar_fully_fixed"),
):
    env["ir.model.data"].create(
        {
            "module": "__ou19__",
            "name": name,
            "model": "resource.calendar",
            "res_id": record.id,
        }
    )

# resource.calendar.tz is dropped and the timezone becomes res.company.tz, one
# per company. The interesting case is a company whose calendars disagree: the
# default calendar's zone has to win, because that is the calendar the company's
# own records are computed against. Planted so the MAJORITY says something else
# -- two calendars in one zone against the default's -- which is the only
# arrangement that can tell the two rules apart.
tz_company = env["res.company"].search([("resource_calendar_id", "!=", False)], limit=1)
assert tz_company, "the seed needs a company with a default working schedule"
tz_company.resource_calendar_id.tz = "Pacific/Chatham"
for n in range(2):
    env["resource.calendar"].create(
        {
            "name": f"ou19-calendar-outvoting-{n}",
            "company_id": tz_company.id,
            "tz": "Asia/Kolkata",
        }
    )
env["ir.model.data"].create(
    {
        "module": "__ou19__",
        "name": "ou19_tz_company",
        "model": "res.company",
        "res_id": tz_company.id,
    }
)

env.cr.commit()
