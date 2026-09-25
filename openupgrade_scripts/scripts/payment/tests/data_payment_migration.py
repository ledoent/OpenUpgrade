env = locals().get("env")

# payment_method_ids is a many2many in 19.0, so one payment.method record serves
# every provider of every company. 20.0 makes it a one2many and each provider
# owns its copies, which payment.provider.copy() creates at install time and an
# upgrade never calls. end-migration replays that copy, driven by the 19.0
# relation table rather than by copying into every provider blindly -- so both
# branches need a witness.
#
# Existing providers are marked rather than created: payment.provider's code is
# a selection each provider module extends, and _setup_provider does work on
# create, so a synthetic one would be testing the fixture rather than the
# migration.
main = env["res.company"].search([], order="id", limit=1)
other = env["res.company"].search([("id", "!=", main.id)], order="id", limit=1)
assert other, "the seed needs a second company for this fixture"

providers = env["payment.provider"].with_context(active_test=False)

# A provider in another company that supported methods in 19.0: the fan-out
# must reach it.
with_methods = providers.search(
    [("company_id", "=", other.id), ("payment_method_ids", "!=", False)], limit=1
)
assert with_methods, "no provider with methods in the second company"
with_methods.name = "ou19-provider-fanout"

# A provider in another company that supported none. The relation table is what
# says which provider supported what, so this one must come out with none --
# copying into every provider regardless would be inventing configuration.
without = providers.search(
    [
        ("company_id", "=", other.id),
        ("id", "!=", with_methods.id),
        ("payment_method_ids", "!=", False),
    ],
    limit=1,
)
assert without, "need a second provider to strip"
without.name = "ou19-provider-nolinks"
env.cr.execute(
    "DELETE FROM payment_method_payment_provider_rel WHERE payment_provider_id = %s",
    (without.id,),
)

# 20.0 replaces state with is_live, which is new and has no default, so every
# provider arrives on False -- a provider that was enabled keeps being offered
# to customers while processing through the test interface.
#
# The seed cannot show this: every one of its 2115 providers is disabled but
# one, which is on test. enabled is the only state the carry has to act on and
# nothing in the seed is in it, so without these two the fix would be asserted
# by a database that cannot disagree.
#
# state is written in SQL because 19.0 refuses to enable a provider whose
# credentials are not filled in, and the credentials are not what is under
# test; pre-migration reads the column either way.
for name, state in (("ou19-provider-live", "enabled"), ("ou19-provider-test", "test")):
    provider = providers.search(
        [("name", "not like", "ou19-provider-%")], order="id", limit=1
    )
    assert provider, f"no provider left to mark for {name}"
    provider.name = name
    env.cr.execute(
        "UPDATE payment_provider SET state = %s WHERE id = %s", (state, provider.id)
    )

env.cr.commit()
