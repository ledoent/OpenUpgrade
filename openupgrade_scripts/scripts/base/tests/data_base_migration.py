env = locals().get("env")

partner_model = env.ref("base.model_res_partner")
group_user = env.ref("base.group_user")
group_system = env.ref("base.group_system")
group_portal = env.ref("base.group_portal")

# --- access lines -----------------------------------------------------------
# read + write only: the letters are not adjacent in the crud alphabet, and
# perm_write maps to "u", which is the pair most likely to be got wrong.
access_ru = env["ir.model.access"].create(
    {
        "name": "ou19-access-ru",
        "model_id": partner_model.id,
        "group_id": group_user.id,
        "perm_read": True,
        "perm_write": True,
        "perm_create": False,
        "perm_unlink": False,
    }
)
# Give it an external id: the script renames the table rather than copying rows
# precisely so that ids, and therefore external ids, survive.
#
# The id is filed under a module that does not exist. _process_end removes data
# rows belonging to modules it has just loaded, so an id claiming to be base's
# would be deleted at the end of the run -- the tests would still pass, being
# at_install, but the fixture would not survive for inspection afterwards.
env["ir.model.data"].create(
    {
        "module": "__ou19__",
        "name": "ou19_access_ru",
        "model": "ir.model.access",
        "res_id": access_ru.id,
    }
)

env["ir.model.access"].create(
    {
        "name": "ou19-access-cd",
        "model_id": partner_model.id,
        "group_id": group_user.id,
        "perm_read": False,
        "perm_write": False,
        "perm_create": True,
        "perm_unlink": True,
    }
)

# Grants nothing, so it has no representation in 20.0 and must be dropped
# along with its external id.
access_none = env["ir.model.access"].create(
    {
        "name": "ou19-access-none",
        "model_id": partner_model.id,
        "group_id": group_user.id,
        "perm_read": False,
        "perm_write": False,
        "perm_create": False,
        "perm_unlink": False,
    }
)
env["ir.model.data"].create(
    {
        "module": "__ou19__",
        "name": "ou19_access_none",
        "model": "ir.model.access",
        "res_id": access_none.id,
    }
)

env["ir.model.access"].create(
    {
        "name": "ou19-access-inactive",
        "model_id": partner_model.id,
        "group_id": group_user.id,
        "perm_read": True,
        "perm_write": False,
        "perm_create": False,
        "perm_unlink": False,
        "active": False,
    }
)

# --- record rules -----------------------------------------------------------
# Three groups: 20.0 keeps one row per group, so this must fan out to three.
rule_multigroup = env["ir.rule"].create(
    {
        "name": "ou19-rule-multigroup",
        "model_id": partner_model.id,
        "groups": [(6, 0, [group_user.id, group_system.id, group_portal.id])],
        "domain_force": "[('id', '!=', 0)]",
        "perm_read": True,
        "perm_write": True,
        "perm_create": False,
        "perm_unlink": False,
    }
)
env["ir.model.data"].create(
    {
        "module": "__ou19__",
        "name": "ou19_rule_multigroup",
        "model": "ir.rule",
        "res_id": rule_multigroup.id,
    }
)

# No groups at all: one row with an empty group_id, which is how core writes
# its own global access lines.
env["ir.rule"].create(
    {
        "name": "ou19-rule-global",
        "model_id": partner_model.id,
        "groups": [(6, 0, [])],
        "domain_force": "[('id', '!=', -4219)]",
        "perm_read": True,
        "perm_write": False,
        "perm_create": False,
        "perm_unlink": False,
    }
)

# ir.rule.name is optional where ir.access.name is required, so this one has to
# come out labelled with its model. Only its domain identifies it afterwards.
env["ir.rule"].create(
    {
        "name": False,
        "model_id": partner_model.id,
        "groups": [(6, 0, [group_user.id])],
        "domain_force": "[('id', '!=', -4220)]",
        "perm_read": True,
        "perm_write": False,
        "perm_create": False,
        "perm_unlink": False,
    }
)

# There is deliberately no rule granting nothing: 19.0 carries a CHECK
# constraint, ir_rule_no_access_rights, that forbids one. ir_model_access
# has no equivalent constraint, which is why the access line above exists.
env.cr.commit()
