"""
Role: Historical Intelligence Records
Initial OSINT threat intelligence records
This file defines the historical OSINT threat intelligence records used to train and test the RAG layer.
Covers predatory youth trends, botnet clusters, and civic distress indicators.
"""

INITIAL_THREAT_RECORDS = [
    {
        "id": "TH-INTEL-001",
        "title": "Operation Midnight Walk Challenge",
        "category": "PREDATORY_YOUTH_TREND",
        "content": "Viral challenge targeting adolescents aged 13-16 on Telegram and X. Involves coercion, night-time location sharing, and secretive group dynamics. Known orchestrator handles: @node_alpha, @dark_nexus."
    },
    {
        "id": "TH-INTEL-002",
        "title": "Blue Whale Successor Campaign Signature",
        "category": "SELF_HARM_COERCION",
        "content": "Psychological pressure tactics used across non-indexed chat channels targeting vulnerable youth in urban clusters. Key indicators: daily tasks assigned by unverified admin accounts."
    },
    {
        "id": "TH-INTEL-003",
        "title": "Botnet Disinformation Cluster - Operation Echo",
        "category": "DISINFORMATION_NETWORK",
        "content": "Coordinated bot farm network propagating panic narratives during public infrastructure events. Primary vectors include synchronized retweets and high-velocity hashtag injection."
    },
    {
        "id": "TH-INTEL-004",
        "title": "Civic Distress Escalation Pattern",
        "category": "CIVIC_INTELLIGENCE",
        "content": "Historical data tracking public anxiety spikes during civil protests. Key indicators include high hostility scores combined with rapid geographical spreading in Tier-2 urban regions."
    }
]