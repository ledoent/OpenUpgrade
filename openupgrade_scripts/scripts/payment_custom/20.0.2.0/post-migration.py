# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _repoint_providers_off_the_dropped_form(env):
    """Move every provider off payment_custom.redirect_form before it is dropped.

    20.0 stops shipping the module's own redirect template and points the two
    providers it declares at payment.generic_redirect_form instead;
    noupdate_changes.xml carries that over. But it can only carry it over for
    records that have an xml_id, and payment.provider rows are routinely
    duplicated by hand -- a production copy here had a third `custom` provider
    with no xml_id still referencing the old view.

    redirect_form_view_id is a plain many2one with a database foreign key, so
    the obsolete-record sweep cannot delete the view while any row points at
    it. It does not fail the upgrade: openupgrade_framework patches the unlink
    to log "Could not delete obsolete record ... of model ir.ui.view" and carry
    on. So the migration ends green with a view 20.0 no longer maintains, still
    rendering the custom provider's payment form, and the next ordinary
    `-u payment_custom` -- a module install, a later patch release -- retries
    the same delete without that patch loaded and stops dead on
    ForeignKeyViolation. Re-pointing here lets the sweep complete during the
    upgrade, which is the only run where the failure is survivable.
    """
    old_view = env.ref("payment_custom.redirect_form", raise_if_not_found=False)
    if not old_view:
        return
    generic = env.ref("payment.generic_redirect_form", raise_if_not_found=False)
    if not generic:
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE payment_provider SET redirect_form_view_id = %s
        WHERE redirect_form_view_id = %s
        """,
        (generic.id, old_view.id),
    )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "payment_custom", "20.0.2.0/noupdate_changes.xml")
    # After load_data: that sets the two xml_id'd providers, this catches any
    # others, and both must happen before the obsolete-record sweep.
    _repoint_providers_off_the_dropped_form(env)
    openupgrade.delete_record_translations(
        env.cr,
        "payment_custom",
        ["payment.payment_provider_pay_on_invoice"],
        ["done_msg"],
    )
    openupgrade.delete_record_translations(
        env.cr,
        "payment_custom",
        ["payment.payment_provider_transfer"],
        ["pending_msg"],
    )
