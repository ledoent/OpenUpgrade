# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _rebuild_the_table_floor_plan(env):
    """Six columns became one JSON blob, and nothing carried the floor plan.

    19.0 held a table's place on the floor in six scalar columns::

        position_h  Float  'Horizontal Position'      default 10
        position_v  Float  'Vertical Position'        default 10
        width       Float  "The table's width in pixels"   default 50
        height      Float  "The table's height in pixels"  default 50
        shape       Selection square/round, required, default 'square'
        color       Char   "a valid 'background' CSS property value"

    20.0 drops all six for a single `floor_plan_layout = fields.Json`. The
    analysis reports that as six unrelated DEL lines and one NEW one, and
    nothing in a schema diff says they are the same information.

    The key names are not guessed. 20.0's own default, written when a restaurant
    is configured, is::

        'floor_plan_layout': {'top': 100, 'left': 100, 'width': 130,
                              'height': 130, 'color': 'green', 'shape': 'square'}

    and `_split_layout_server_data` puts everything that is not a model column
    into that same dictionary. `top` is the vertical offset and `left` the
    horizontal one, which is the only way round that matches CSS and the
    defaults above.

    Without this the column is NULL on every table and the point of sale draws
    the floor from nothing: on the seed that is 27 tables holding **25 distinct
    positions**, every one of them lost. `color` carries across as it stands --
    19.0 already stored a CSS value, `rgb(53,211,116)` in the seed, and 20.0's
    examples are CSS values too.

    Nulls are stripped rather than written as JSON `null`: 20.0 spreads the
    dictionary into the record it sends the browser (`{'id': table.id,
    **(table.floor_plan_layout or {})}`), where a key present-but-null is not
    the same as a key absent. One seeded table has no colour, so this is not
    hypothetical.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE restaurant_table
        SET floor_plan_layout = jsonb_strip_nulls(
            jsonb_build_object(
                'left', position_h,
                'top', position_v,
                'width', width,
                'height', height,
                'shape', shape,
                'color', color
            )
        )
        WHERE floor_plan_layout IS NULL
        """,
    )


def _report_the_floor_background(env):
    """restaurant.floor's background has nowhere to go in 20.0.

    19.0 gave a floor a `background_color` ("html-compatible") and a
    `background_image`. 20.0 replaces them with the same `floor_plan_layout`
    JSON it gives a table -- but unlike the table's, whose keys 20.0 writes and
    reads by name, **neither `background_color` nor `background_image` appears
    anywhere in 20.0's pos_restaurant**, in Python or in the front end.

    So there is no key to carry them into. Inventing one would put data in a
    blob nothing reads and make the loss harder to find later, not easier. The
    count is reported and the 19.0 columns are left where they are, which is
    where an administrator can still see them.
    """
    env.cr.execute(
        "SELECT count(*) FROM restaurant_floor WHERE background_color IS NOT NULL"
    )
    coloured = env.cr.fetchone()[0]
    if coloured:
        openupgrade.message(
            env.cr,
            "pos_restaurant",
            False,
            False,
            "%s restaurant floor(s) had a background colour; 20.0 has no key for "
            "it in floor_plan_layout and reads neither background_color nor "
            "background_image, so it was not carried over",
            coloured,
        )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "pos_restaurant", "20.0.1.0/noupdate_changes.xml")
    _rebuild_the_table_floor_plan(env)
    _report_the_floor_background(env)
