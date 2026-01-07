"""
`utils.get_custom_agents` module: A utility for retrieving the custom user agents for a domain from config.
"""

from flask import current_app


def get_custom_agents(domain):
    for d, agents in current_app.config["CUSTOM_USER_AGENT_DOMAINS"].items():
        if d in domain:
            return agents
    return None
