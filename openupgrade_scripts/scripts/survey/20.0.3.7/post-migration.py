# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _map_certification_layout(env):
    """20.0 re-cut the certificate layouts along both axes.

    19.0 offered modern / classic in purple, blue or gold. 20.0 offers modern,
    minimal, classic-1 and classic-2, each in the company colour or black. No
    19.0 value survives, so every certified survey keeps a key the selection no
    longer declares -- the layout silently falls back and the field reads blank.

    left() rather than LIKE 'modern%': openupgradelib's logged_query hands the
    query to psycopg2 with an args tuple, so a literal % is read as a parameter
    placeholder and the call dies on IndexError before reaching the database.

    The style is what carries over; the colour does not, because 20.0 has no
    purple, blue or gold. The company variant is the closer of the two on
    offer: those three were brand colours, not black. classic becomes
    classic-1, which is the layout 20.0 kept under that name.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE survey_survey SET certification_report_layout = CASE
            WHEN left(certification_report_layout, 6) = 'modern'
                THEN 'modern_company'
            ELSE 'classic-1_company'
        END
        WHERE certification_report_layout IN (
            'modern_purple', 'modern_blue', 'modern_gold',
            'classic_purple', 'classic_blue', 'classic_gold'
        )
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "survey", "20.0.3.7/noupdate_changes.xml")
    _map_certification_layout(env)
