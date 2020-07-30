from sqlalchemy import (
    Column,
    DateTime,
    Float,
    String,
    Integer,
)


class PackageReportColumnsMixin:
    """
    mix into derived tables and views using PackageReport as score inputs
    and returning a superset of PackageReport columns
    """

    package = Column(String(200))
    version = Column(String(200))
    release_date = Column(DateTime)
    scoring_date = Column(DateTime)
    top_score = Column(Integer)
    npmsio_score = Column(Float)
    npmsio_scored_package_version = Column(String)
    directVulnsCritical_score = Column(Integer)
    directVulnsHigh_score = Column(Integer)
    directVulnsMedium_score = Column(Integer)
    directVulnsLow_score = Column(Integer)
    indirectVulnsCritical_score = Column(Integer)
    indirectVulnsHigh_score = Column(Integer)
    indirectVulnsMedium_score = Column(Integer)
    indirectVulnsLow_score = Column(Integer)
    authors = Column(Integer)
    contributors = Column(Integer)
    immediate_deps = Column(Integer)
    all_deps = Column(Integer)
    graph_id = Column(Integer, nullable=True)
