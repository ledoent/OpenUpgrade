# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# slide.slide.date_published is spelled published_date in 20.0, the same name
# website's publishable mixin already used elsewhere. Nothing in the analysis
# links the two -- it reports a DEL and a NEW -- so without this the column is
# created empty and every slide loses the date it went live. 39 of them on the
# seed.
#
# Not publish_on, which the analysis also offers as a NEW datetime on this
# model: that is the mixin's "Auto publish on", a future time to publish at,
# and writing a past publication date into it would schedule nothing and mean
# something else.
_renamed_fields = [
    ("slide.slide", "slide_slide", "date_published", "published_date"),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_fields(env, _renamed_fields)
