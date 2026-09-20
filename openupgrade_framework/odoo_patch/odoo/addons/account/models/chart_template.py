# Copyright Odoo Community Association (OCA)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""account is not a dependency of this module, so the patch is optional."""
try:
    from odoo.addons.account.models.chart_template import AccountChartTemplate
except ImportError:
    AccountChartTemplate = None


def _get_chart_template_mapping(self, get_all=False):
    """Resolve every chart template, not only the ones still offered.

    account is inconsistent about this. _load_translations picks the companies
    to work on with

        self._get_chart_template_mapping(get_all=True)

    while _parse_csv resolves the very same codes against the default,
    visible-only mapping and subscripts the result:

        self._get_chart_template_mapping().get(template_code)['module']

    A company sitting on a template that 20.0 stopped offering therefore passes
    the filter and then fails the lookup. 19.0's plain "fr" is one: 20.0 keeps
    it as the parent of the visible French variants, so an existing FR company
    ends the load with "'NoneType' object is not subscriptable" after every
    module has already migrated.

    A database being upgraded has whatever templates it has, and they all need
    to resolve.
    """
    return AccountChartTemplate._get_chart_template_mapping._original_method(
        self, get_all=True
    )


if AccountChartTemplate is not None:
    _get_chart_template_mapping._original_method = (
        AccountChartTemplate._get_chart_template_mapping
    )
    AccountChartTemplate._get_chart_template_mapping = _get_chart_template_mapping
