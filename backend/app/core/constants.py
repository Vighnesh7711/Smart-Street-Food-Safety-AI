"""Shared constants that must not be duplicated.

Anything here appears in more than one place, where two copies would drift.
"""

#: Advisory notice shown wherever a hygiene or scan result is presented to a
#: non-expert audience.
#:
#: Defined once because it is the single sentence that keeps this product
#: honest: a vendor must never be able to present a score as certification,
#: and a consumer must never read one as an inspection result. The hygienist
#: endpoint, the public stall profile, and the mobile result screens all
#: render this exact string, and the API returns it in the payload so a
#: client cannot drop it by not rendering the copy.
DISCLAIMER = (
    "AI-assisted assessment, not an official certification. "
    "It is a guide to help you improve, not a licence or a clearance."
)

#: Shorter form for tight layouts (public pages, badges) where the full
#: sentence would dominate. Deliberately still contains "not ... official".
DISCLAIMER_SHORT = "AI-assisted, not an official certification."
