# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _restore_what_each_collaborator_was_allowed_to_do(env):
    """project.collaborator.limited_access becomes a three-way access_mode.

    19.0 had `limited_access = fields.Boolean('Limited Access', default=False)`.
    20.0 replaces it with `access_mode` -- view / edit / advanced_edit -- which
    is **required and defaults to 'view'**, so the upgrade demotes every
    collaborator to a reader.

    That is a real loss of granted rights, not a cosmetic one. A 19.0
    collaborator exists because a project was shared for EDITING; a read-only
    share did not create one at all. After the upgrade those portal users can
    open the project and change nothing.

    The mapping is taken from the same method in both versions rather than from
    the label text, which is what makes it defensible::

        19.0  def _add_collaborators(self, partners, limited_access=False)
        20.0  def _add_collaborators(self, partners, access_mode='advanced_edit')

    The default argument of one is the default argument of the other, so
    `limited_access = False` is `advanced_edit`. The remaining True maps to
    'edit': 20.0 tests the right to edit as `access_mode in ('edit',
    'advanced_edit')` (project_task.py:2281) and reserves 'advanced_edit' alone
    for the extra capability it gates at project_task.py:1130 -- which is what
    "limited" meant.

    Nothing maps to 'view'. It is 20.0's spelling of a read-only share, a thing
    19.0 did not record here.
    """
    if not openupgrade.column_exists(env.cr, "project_collaborator", "limited_access"):
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE project_collaborator
        SET access_mode = CASE WHEN limited_access THEN 'edit' ELSE 'advanced_edit' END
        WHERE access_mode IS DISTINCT FROM
              CASE WHEN limited_access THEN 'edit' ELSE 'advanced_edit' END
        """,
    )
    if env.cr.rowcount:
        openupgrade.message(
            env.cr,
            "project",
            False,
            False,
            "project.collaborator: restored the editing rights of %s "
            "collaborator(s); 20.0's access_mode defaults to 'view', which would "
            "have left every shared-project portal user able to change nothing",
            env.cr.rowcount,
        )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "project", "20.0.1.4/noupdate_changes.xml")
    _restore_what_each_collaborator_was_allowed_to_do(env)
