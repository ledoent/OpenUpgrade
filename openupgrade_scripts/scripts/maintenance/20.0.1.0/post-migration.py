# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _carry_completion_into_state(env):
    """19.0 recorded that a request was finished on its STAGE; 20.0 on the request.

    19.0 had no lifecycle field. A request was finished when it sat in a stage
    whose `maintenance.stage.done` was set -- "Repaired" and "Scrap" in the
    standard data -- and `write` read `stage_id.done` to decide whether to spawn
    the next occurrence of a recurring request.

    20.0 adds `maintenance.request.state`, required, defaulting to 'normal'
    ("In Progress"), and moves every consumer onto it: `maintenance_open_count`
    counts `state not in ('done', 'cancelled')`, the equipment's effective date
    -- and so its MTBF -- counts corrective requests with `state == 'done'`, and
    `write` maintains `close_date` from it.

    The column is new, required and defaulted, so the ORM fills every existing
    row with 'normal' and nothing raises: every request ever completed comes out
    reading as still in progress, and the equipment statistics computed from
    them read as though no maintenance had ever been finished.

    The seed shows the contradiction directly -- two of its five requests carry
    a `close_date` while reading "In Progress", a combination 20.0's own
    `create` exists to prevent::

        if request.close_date and request.state != 'done':
            request.close_date = False

    Only rows still on the ORM's default are touched, so nothing another script
    has already decided is overwritten.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE maintenance_request r
        SET state = 'done'
        FROM maintenance_stage s
        WHERE s.id = r.stage_id AND s.done AND r.state = 'normal'
        """,
    )


def _carry_the_assignee_into_the_user_list(env):
    """user_id (many2one) becomes user_ids (many2many), and nothing carries it.

    19.0 assigned a request to one technician through `user_id`. 20.0 drops that
    field for `user_ids`, a many2many whose compute only ever adds the
    equipment's technician::

        @api.depends('company_id', 'equipment_id')
        def _compute_user_ids(self):
            ...
            technician = (request.equipment_id.technician_user_id
                          or request.equipment_id.category_id.technician_user_id)

    So a request assigned to anyone else -- a stand-in, a second-line engineer,
    whoever took it over -- comes out assigned to nobody, or to the wrong person.

    **This seed cannot show it.** All five of its requests are assigned to
    exactly the technician their equipment carries, so the many2many comes out
    right by coincidence and every after-the-fact comparison agrees. The evidence
    is the pair of field definitions, and the migration test builds the row the
    seed lacks: a request assigned to someone who is not the equipment's
    technician.

    `user_id` is read straight rather than through a legacy name: 20.0 declares
    no field of that name on this model, so the upgrade leaves the column alone
    and nothing can have overwritten it.

    20.0's own company filter is applied rather than ignored. `_compute_user_ids`
    drops a user who does not belong to the request's company, so inserting one
    here would put a name on the request that the next recompute takes off again.
    The ones that excludes are reported rather than dropped in silence.
    """
    openupgrade.logged_query(
        env.cr,
        """
        INSERT INTO maintenance_request_res_users_rel
            (maintenance_request_id, res_users_id)
        SELECT r.id, r.user_id
        FROM maintenance_request r
        JOIN res_company_users_rel cu
          ON cu.user_id = r.user_id AND cu.cid = r.company_id
        WHERE r.user_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """,
    )
    env.cr.execute(
        """
        SELECT count(*)
        FROM maintenance_request r
        WHERE r.user_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM res_company_users_rel cu
              WHERE cu.user_id = r.user_id AND cu.cid = r.company_id
          )
        """
    )
    outside = env.cr.fetchone()[0]
    if outside:
        openupgrade.message(
            env.cr,
            "maintenance",
            False,
            False,
            "%s maintenance request(s) were assigned to a user who does not "
            "belong to the request's company; 20.0's _compute_user_ids removes "
            "such a user, so the assignment was not carried over",
            outside,
        )


def _report_the_kanban_state_that_has_no_home(env):
    """19.0's kanban_state is gone and no 20.0 value certainly means the same.

    19.0 carried a review indicator beside the stage: 'normal' (In Progress),
    'blocked' (Blocked) and 'done' (Ready for next stage). 20.0 has no separate
    indicator; `state` covers that axis with 'changes_requested' and 'approved'.

    The shapes line up loosely and the meanings do not. "Blocked" says the work
    cannot proceed -- a missing part, a machine in use -- where "Changes
    Requested" says a reviewer asked for something, so a request blocked on a
    delivery would come out claiming a review that never happened. Nothing is
    written, the count is reported, and the 19.0 answer stays in its column where
    an administrator can act on it.

    Every request in this seed is on 'normal', which is what `state` defaults to
    anyway, so on a standard database this reports nothing at all.
    """
    env.cr.execute(
        """
        SELECT kanban_state, count(*) FROM maintenance_request
        WHERE kanban_state IS NOT NULL AND kanban_state != 'normal'
        GROUP BY kanban_state
        """
    )
    for value, count in env.cr.fetchall():
        openupgrade.message(
            env.cr,
            "maintenance",
            False,
            False,
            "%s maintenance request(s) were on kanban_state '%s'; 20.0 has no "
            "value that certainly means the same, so state was left alone and "
            "maintenance_request.kanban_state still holds the 19.0 answer",
            count,
            value,
        )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "maintenance", "20.0.1.0/noupdate_changes.xml")
    _carry_completion_into_state(env)
    _carry_the_assignee_into_the_user_list(env)
    _report_the_kanban_state_that_has_no_home(env)
