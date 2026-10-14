# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _rename_the_service_date(env):
    """A service log's `date` becomes `date_from`, and nothing says so.

    20.0 gives a service record a span instead of a point: `date` is dropped,
    `date_from` and `date_to` are added, and a CHECK enforces the order::

        CHECK((date_to IS NULL) OR (date_from IS NOT NULL AND date_to >= date_from))

    The analysis reports a DEL and two NEWs, which reads as three unrelated
    changes. The field definitions say otherwise -- 20.0's `date_from` carries
    19.0's `date` help text **unchanged**, "Date when the cost has been
    executed", and the same `default=fields.Date.context_today`:

        19.0  date      = fields.Date(help='Date when the cost has been executed', ...)
        20.0  date_from = fields.Date(string='Start of Service',
                                      help='Date when the cost has been executed', ...)

    and 20.0's own `_get_odometer`-adjacent code passes `date_from` wherever it
    needs the service's date.

    Because `date_from` carries that default, nothing about the upgrade looks
    wrong without this: the column is created, every existing row is filled with
    **the day the upgrade ran**, and every service in the vehicle's history
    silently moves to today. The seed's six service logs hold six different
    dates; all six come out identical.

    Renaming in pre-migration carries the values and leaves `date_to` null,
    which the CHECK allows.
    """
    if openupgrade.column_exists(env.cr, "fleet_vehicle_log_services", "date"):
        openupgrade.rename_fields(
            env,
            [
                (
                    "fleet.vehicle.log.services",
                    "fleet_vehicle_log_services",
                    "date",
                    "date_from",
                )
            ],
        )


@openupgrade.migrate()
def migrate(env, version):
    _rename_the_service_date(env)
