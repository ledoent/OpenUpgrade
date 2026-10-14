env = locals().get("env")

# project.collaborator.limited_access (boolean) becomes access_mode, a required
# selection defaulting to 'view'. Both 19.0 values have to be planted, because
# they map to different 20.0 keys and a fixture carrying only one would pass
# against a script that wrote a single value for everybody.
#
# The seed holds one collaborator, so a second is created rather than borrowed.
project = env["project.project"].search([], order="id", limit=1)
assert project, "the seed needs a project to share"

partners = env["res.partner"].search([("email", "!=", False)], order="id", limit=2)
assert len(partners) == 2, "the seed needs two partners with an email to share with"

existing = env["project.collaborator"].search([("project_id", "=", project.id)])
existing.unlink()

env["project.collaborator"].create(
    [
        {
            # Not limited: 19.0's own default, and the one that maps to
            # 'advanced_edit' -- the default of the same method in 20.0.
            "project_id": project.id,
            "partner_id": partners[0].id,
            "limited_access": False,
        },
        {
            "project_id": project.id,
            "partner_id": partners[1].id,
            "limited_access": True,
        },
    ]
)

env.cr.commit()
