# Copyright Odoo Community Association (OCA)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""mail is not a dependency of this module, so the patch is optional."""

try:
    from odoo.addons.mail.models.mail_activity import MailActivity
except ImportError:
    MailActivity = None


def _get_phone_numbers_by_activity(self):
    """Skip activities pointing at a model the registry does not have yet.

    The method resolves self.env[res_model] for every distinct model it finds.
    During a major upgrade the activities of a module that has not been loaded
    yet are already in the table, so the lookup raises KeyError and takes the
    whole upgrade down -- a mail.activity on event.event kills the run while
    mail is being updated and event has not been reached.
    """
    known = self.filtered(lambda a: a.res_model in self.env.registry.models)
    return MailActivity._get_phone_numbers_by_activity._original_method(known)


if MailActivity is not None:
    _get_phone_numbers_by_activity._original_method = (
        MailActivity._get_phone_numbers_by_activity
    )
    MailActivity._get_phone_numbers_by_activity = _get_phone_numbers_by_activity
