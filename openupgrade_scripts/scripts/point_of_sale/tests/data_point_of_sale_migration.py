env = locals().get("env")

# pos.payment.method.type is computed in 19.0 and stored + required in 20.0, so
# the column starts empty and has to be derived. 19.0's own _compute_type reads
# the JOURNAL, not anything on the method, and falls through to pay_later when
# the journal is neither cash nor bank -- including when there is none. One
# method per branch.
company = env.company
journals = env["account.journal"]


def _journal(kind):
    found = journals.search(
        [("type", "=", kind), ("company_id", "=", company.id)], limit=1
    )
    return found or journals.create(
        {
            "name": f"ou19-{kind}",
            "code": f"OU{kind[:2].upper()}",
            "type": kind,
            "company_id": company.id,
        }
    )


method = env["pos.payment.method"]
method.create(
    {
        "name": "ou19-pm-cash",
        "journal_id": _journal("cash").id,
        "company_id": company.id,
    }
)
method.create(
    {
        "name": "ou19-pm-bank",
        "journal_id": _journal("bank").id,
        "company_id": company.id,
    }
)
# No journal at all: this is the branch is_cash_count cannot distinguish, since
# it is False here and False on a bank method alike.
method.create({"name": "ou19-pm-none", "company_id": company.id})

env.cr.commit()
