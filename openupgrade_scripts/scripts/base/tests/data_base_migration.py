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

# --- res.partner.bank account number rename ---------------------------------
# 20.0 spells the field out: acc_number -> account_number, and
# sanitized_acc_number -> sanitized_account_number. Both are stored, so the
# values have to be carried across rather than recomputed.
#
# The number is written with punctuation and lower case on purpose: the
# sanitized column strips non-alphanumerics and upper-cases, so a test that
# only checked account_number would pass even if the sanitized half had been
# left to a compute that never ran.
partner_ru = env["res.partner"].create(
    {
        "name": "ou19-bank-partner",
        # The partner's country is deliberately NOT the bank's. 20.0's
        # country_id is a stored precompute that reads partner_id.country_id,
        # yet it sits in the inlined bank-address block -- so a bank abroad
        # silently acquires the holder's country, and only a disagreement here
        # can catch it.
        "country_id": env.ref("base.fr").id,
    }
)
# 20.0 deletes res.bank and inlines its name, BIC and address onto the account.
# Values are planted on every field that has a destination, plus email and phone
# which have none, so the carry and the report are both exercised.
bank_ru = env["res.bank"].create(
    {
        "name": "ou19-bank-name",
        "bic": "OU19BICXXX",
        "street": "ou19-bank-street",
        "street2": "ou19-bank-street2",
        "zip": "94105",
        "city": "ou19-bank-city",
        # Searched rather than env.ref'd: a missing xmlid raises, and a raise
        # here aborts the whole fixture batch for every module, not just base.
        "state": env["res.country.state"]
        .search([("country_id.code", "=", "US"), ("code", "=", "CA")], limit=1)
        .id,
        "country": env.ref("base.us").id,
        "email": "ou19-bank@example.org",
        "phone": "+1 555 0199",
    }
)
env["res.partner.bank"].create(
    {
        "acc_number": "ou19-acct 0042/7",
        "partner_id": partner_ru.id,
        "bank_id": bank_ru.id,
        # acc_holder_name -> holder_name is the third rename on this model and
        # the one with teeth. The holder is written DIFFERENT from the partner
        # name on purpose: 20.0's _compute_account_holder_name fills an empty
        # holder_name with partner_id.name, so a holder that merely echoed the
        # partner would come out right whether the rename ran or not, and the
        # assertion would pass for the wrong reason.
        "acc_holder_name": "ou19-holder-not-the-partner",
    }
)

# company_registry is dropped for the additional_identifiers Json. Two partners,
# because the carry has two outcomes worth separating: a value that satisfies its
# country's own identifier format goes under that key, and one that satisfies
# nothing falls back to 'OTHER' -- which 20.0 then hides for any country that has
# an identifier of its own.
#
# The first value has to pass FR_SIREN's real validator, which is a Luhn check
# over 9 digits -- 404833048 sums to 40 with the even positions doubled. An
# invented number would fail the check digit and land in the fallback branch,
# which is what the second partner is for.
env["res.partner"].create(
    {
        "name": "ou19-registry-structured",
        "country_id": env.ref("base.fr").id,
        "company_registry": "404833048",
    }
)
env["res.partner"].create(
    {
        "name": "ou19-registry-unstructured",
        "country_id": env.ref("base.fr").id,
        "company_registry": "ou19-not-a-siren",
    }
)

env.cr.commit()
