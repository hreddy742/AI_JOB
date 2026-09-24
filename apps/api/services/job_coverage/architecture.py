"""ASCII architecture diagram and worker topology helpers."""

ARCHITECTURE_DIAGRAM = r"""
                        +--------------------------+
                        |  Scheduler / ARQ Cron    |
                        +------------+-------------+
                                     |
                   +-----------------+-----------------+
                   |                                   |
         +---------v---------+               +---------v---------+
         | Tier-1 Connectors |               | ATS Detection     |
         | (APIs/feeds)      |               | + Tier-2 Scrapers |
         +---------+---------+               +---------+---------+
                   |                                   |
                   +-----------------+-----------------+
                                     |
                             +-------v-------+
                             | Normalization |
                             |  JobPosting   |
                             +-------+-------+
                                     |
                             +-------v-------+
                             | Dedupe         |
                             | primary+fuzzy  |
                             +-------+--------+
                                     |
                             +-------v--------+
                             | Redis Streams  |
                             | ingestion.raw  |
                             +-------+--------+
                                     |
                    +----------------+----------------+
                    |                                 |
             +------v------+                   +------v------+
             | PostgreSQL  |                   | Typesense   |
             | + pgvector  |                   | index       |
             +------+------+                   +------+------+
                    |                                 |
                    +---------------+-----------------+
                                    |
                             +------v------+
                             | Ranking/UI  |
                             +-------------+
"""
