# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_legacy_rel = openupgrade.get_legacy_name("payment_method_payment_provider_rel")


def _source_provider_by_code(env):
    """Pick, per provider code, the provider whose 20.0 payment methods to copy.

    The provider modules ship their methods against one provider each -- the one
    their own data file references -- so after the upgrade exactly those
    providers own methods. Every other provider of the same code is a per-company
    duplicate that core created with copy(), and is what needs filling in.
    """
    env.cr.execute(
        """
        SELECT p.code, min(p.id)
        FROM payment_provider p
        JOIN payment_method m ON m.provider_id = p.id
        GROUP BY p.code
        """
    )
    return dict(env.cr.fetchall())


def _restore_per_company_methods(env):
    """Give every provider back the payment methods it had in 19.0.

    19.0 held the link in a many2many, so one payment.method record served every
    provider of every company. 20.0 makes payment_method_ids a one2many and each
    provider owns its own copies: payment.provider.copy() duplicates the primary
    methods and their brands into the new provider, and that is how a fresh
    install populates the companies beyond the first.

    An upgrade never calls copy(), so without this only the providers whose
    module data named them come out with methods and every other company is left
    with none. The 19.0 relation table is the record of which provider supported
    what, so it drives the fan-out rather than copying blindly into all of them.
    """
    if not openupgrade.table_exists(env.cr, _legacy_rel):
        return
    sources = _source_provider_by_code(env)
    # Providers that supported methods in 19.0 but came out of the upgrade with
    # none of their own.
    env.cr.execute(
        f"""
        SELECT DISTINCT p.id, p.code
        FROM {_legacy_rel} r
        JOIN payment_provider p ON p.id = r.payment_provider_id
        WHERE NOT EXISTS (
            SELECT 1 FROM payment_method m WHERE m.provider_id = p.id
        )
        ORDER BY p.id
        """
    )
    targets = env.cr.fetchall()
    provider_model = env["payment.provider"]
    copied = 0
    served = set()
    for provider_id, code in targets:
        source_id = sources.get(code)
        if not source_id or source_id == provider_id:
            continue
        source = provider_model.browse(source_id)
        primary = source.payment_method_ids.filtered("is_primary")
        if not primary:
            continue
        # Mirrors payment.provider.copy(): the brands have to be copied against
        # the copy of their own primary method, not the original.
        new_primary = primary.copy({"provider_id": provider_id})
        for old, new in zip(primary, new_primary, strict=True):
            old.brand_ids.copy(
                {"provider_id": provider_id, "primary_payment_method_id": new.id}
            )
        copied += len(primary)
        served.add(provider_id)
    if copied:
        openupgrade.message(
            env.cr,
            "payment",
            False,
            False,
            "Copied %s payment methods into %s providers that had them through "
            "the 19.0 many2many",
            copied,
            len(served),
        )
    # A provider whose code no longer owns any method in 20.0 has nothing to copy
    # from. Every such provider here is a custom one: 19.0 had three custom modes
    # and 20.0 has two, with the methods moved onto providers that 19.0 never
    # shipped, so restoring them is a payment_custom question rather than a
    # generic one.
    unserved = [pid for pid, _code in targets if pid not in served]
    if unserved:
        openupgrade.message(
            env.cr,
            "payment",
            False,
            False,
            "%s providers supported payment methods in 19.0 whose code owns none "
            "in 20.0 and were left without any; they are custom providers, whose "
            "modes changed in 20.0",
            len(unserved),
        )


def _retarget_references(env, table):
    """Move a reference off a 19.0 method onto its owner's copy.

    A 19.0 payment.method was provider-agnostic, so the record a transaction or
    token points at says nothing about which provider handled it; the row's own
    provider_id does. The replacement is that provider's method of the same code.
    """
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE {table} t
        SET payment_method_id = new_method.id
        FROM payment_method old_method
        JOIN payment_method new_method ON new_method.code = old_method.code
        WHERE t.payment_method_id = old_method.id
          AND old_method.provider_id IS NULL
          AND new_method.provider_id = t.provider_id
        """,
    )


def _drop_obsolete_methods(env):
    """Remove the 19.0 payment.method records that 20.0 has no place for.

    They are provider-agnostic, so provider_id cannot be filled for them, and
    20.0 declares it required -- the upgrade logs "Constraint not added: column
    provider_id of relation payment_method contains null values" and carries on
    without it. They are noupdate records, so _process_end leaves them behind
    along with their external ids.

    Anything still referenced is left alone rather than cascading the delete into
    a customer's transactions; provider_id then stays nullable, which is the same
    state the upgrade reaches today.
    """
    for table in ("payment_transaction", "payment_token"):
        _retarget_references(env, table)
    openupgrade.logged_query(
        env.cr,
        """
        DELETE FROM ir_model_data
        WHERE model = 'payment.method'
          AND res_id IN (
            SELECT m.id FROM payment_method m
            WHERE m.provider_id IS NULL
              AND m.code != 'unknown'
              AND NOT EXISTS (SELECT 1 FROM payment_transaction t
                              WHERE t.payment_method_id = m.id)
              AND NOT EXISTS (SELECT 1 FROM payment_token k
                              WHERE k.payment_method_id = m.id)
          )
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        DELETE FROM payment_method m
        WHERE m.provider_id IS NULL
          AND m.code != 'unknown'
          AND NOT EXISTS (SELECT 1 FROM payment_transaction t
                          WHERE t.payment_method_id = m.id)
          AND NOT EXISTS (SELECT 1 FROM payment_token k
                          WHERE k.payment_method_id = m.id)
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    _restore_per_company_methods(env)
    _drop_obsolete_methods(env)
