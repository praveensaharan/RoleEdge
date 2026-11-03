"""CareCircle: family-care chat with an AI helper (Saathi).

Packages, from the bottom up (an import may only point down this list; see ARCHITECTURE.md):

    config     settings and paths (the only reader of environment variables)
    models     domain data (pydantic), no I/O
    llm        providers (Meta, Azure), cache, usage ledger
    content    shared item -> digest -> checker
    checkin    daily check-in call agent
    render     cards, explainer videos, calendar files
    chat       chat playground web API
    cli        command line entry point
"""

__version__ = "0.1.0"
