# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# The two models 20.0's pos_event gives a uuid, with the table each is stored in.
_UUID_TABLES = (
    ("event.registration", "event_registration"),
    ("event.registration.answer", "event_registration_answer"),
)


def _regenerate_the_shared_uuids(env, table):
    """Every pre-existing row came out of the upgrade carrying the SAME uuid.

    20.0's pos_event adds a uuid to both models::

        uuid = fields.Char(string='Uuid', readonly=True,
                           default=lambda self: str(uuid4()), copy=False)

    A column default is evaluated ONCE when the ORM creates the column, not once
    per row, so every row that already existed is written the same value. On the
    seed that is all 29 registrations sharing one uuid and all 12 answers
    sharing another -- and there is no unique index on either column, so nothing
    raises and the upgrade reports success.

    The value is not cosmetic. Both fields are in `_load_pos_data_fields`, which
    is the payload the point of sale front end loads and then matches records
    by; identical uuids are indistinguishable records to it. `copy=False` says
    the same thing in the model: this is an identity, and duplicating it is
    never right.

    Regenerating is safe here precisely because the uuid carries nothing from
    19.0. It is `readonly=True`, machine-generated, and 19.0 had no such column
    at all, so there is no 19.0 answer to preserve -- only an identity to make
    unique. That is what separates this from a value the upgrade defaulted over:
    where the old version DID record something, inventing a replacement would be
    a guess, and this is not one.

    Only rows whose uuid is shared are touched, so a row that already holds a
    unique value -- one created after the upgrade, or on a second run -- is left
    alone, and running this twice is a no-op.
    """
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE {table}
        SET uuid = gen_random_uuid()::text
        WHERE uuid IN (
            SELECT uuid FROM {table}
            WHERE uuid IS NOT NULL
            GROUP BY uuid HAVING count(*) > 1
        )
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    for model, table in _UUID_TABLES:
        if openupgrade.column_exists(env.cr, table, "uuid"):
            _regenerate_the_shared_uuids(env, table)
        else:
            openupgrade.message(
                env.cr,
                "pos_event",
                False,
                False,
                "%s has no uuid column, so the duplicate-identity repair was "
                "skipped; 20.0 declares one, so this means the model changed "
                "again and the repair needs re-reading",
                model,
            )
