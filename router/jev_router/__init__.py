"""jev-router: an open-source LLM router that uses TypeSafe's Jev.

Submodules are imported explicitly so the decision layer (``jev_router.deciders``)
stays free of the proxy's dependencies:

    from jev_router.deciders import JevDecider
    from jev_router.config import load_config  # requires pyyaml
    from jev_router.hook import JevRouterLogger  # requires litellm
"""

__version__ = "0.0.1"
