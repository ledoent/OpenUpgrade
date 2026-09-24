# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _date_the_points_from_when_they_changed(env):
    """Every loyalty history line came out dated the moment the upgrade ran.

    19.0's loyalty.history recorded no date at all. It carried `description`,
    `issued`, `used` and the order reference, and ordered itself by `_order =
    'id desc'`.

    20.0 adds `points_changed_date`, **required**, and makes it the first key of
    both orderings the model uses::

        _order = "points_changed_date desc, id desc"
        FIFO_ORDER = "expiration_date ASC NULLS LAST, points_changed_date ASC, id ASC"

    A required column with a time default is still filled ONCE, when the ORM
    creates it, so every pre-existing line comes out stamped with the moment of
    the upgrade -- all 39 of the seed's on a single timestamp. Nothing raises:
    the NOT NULL is satisfied precisely because the column is full. That is what
    makes it worth checking, and the previous annotation on this line read the
    clean constraint as evidence that the rows were fine.

    `create_date` is the right source and needs no guessing. A history line is
    written when the points change, so the row's creation IS the event's date --
    which is why 19.0 never needed a separate column. On the seed it restores
    **7 distinct timestamps** in place of one.

    Only rows still carrying the stamp are touched, identified as "every row
    sharing the single most common value", so a line written after the upgrade
    keeps its own date and a second run changes nothing.

    `expiration_date` is deliberately NOT filled. It is the other half of
    FIFO_ORDER, but 19.0 recorded no expiry and 20.0 derives it from the
    programme's new `expire_after`; inventing one here would expire points on a
    date nobody chose.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE loyalty_history
        SET points_changed_date = create_date
        WHERE create_date IS NOT NULL
          AND points_changed_date IN (
              SELECT points_changed_date FROM loyalty_history
              GROUP BY points_changed_date HAVING count(*) > 1
          )
          AND points_changed_date <> create_date
        """,
    )
    env.cr.execute("SELECT count(*) FROM loyalty_history WHERE create_date IS NULL")
    undated = env.cr.fetchone()[0]
    if undated:
        openupgrade.message(
            env.cr,
            "loyalty",
            False,
            False,
            "%s loyalty history line(s) have no create_date, so the date the "
            "points changed could not be restored and they keep the timestamp "
            "the upgrade wrote",
            undated,
        )


@openupgrade.migrate()
def migrate(env, version):
    _date_the_points_from_when_they_changed(env)
