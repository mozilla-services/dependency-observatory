# Placeholder for model code

import os
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

from flask_sqlalchemy import SQLAlchemy
import networkx as nx
from networkx.drawing.nx_pydot import to_pydot
import pydot
from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import backref, relationship
from sqlalchemy.schema import Table
from sqlalchemy import func

from depobs.scanner.db.schema import (
    Advisory,
    Base as scanner_schema_declarative_base,
    NPMRegistryEntry,
    NPMSIOScore,
    PackageGraph,
    PackageLink,
    PackageVersion,
)
from depobs.scanner.pipelines.save_to_db import (
    insert_npmsio_data,
    insert_npm_registry_data,
)
from depobs.database.mixins import TaskIDMixin


log = logging.getLogger(__name__)


db = SQLAlchemy()


class Dependency(db.Model):
    __tablename__ = "package_dependencies"

    depends_on_id = Column(Integer, ForeignKey("reports.id"), primary_key=True)
    used_by_id = Column(Integer, ForeignKey("reports.id"), primary_key=True)


class PackageReport(TaskIDMixin, db.Model):
    __tablename__ = "reports"

    id = Column("id", Integer, primary_key=True)

    package = Column(String(200))
    version = Column(String(200))
    status = Column(String(200))
    release_date = Column(DateTime)
    scoring_date = Column(DateTime)
    top_score = Column(Integer)
    npmsio_score = Column(Float)
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

    # this relationship is used for persistence
    dependencies = relationship(
        "PackageReport",
        secondary=Dependency.__table__,
        primaryjoin=id == Dependency.__table__.c.depends_on_id,
        secondaryjoin=id == Dependency.__table__.c.used_by_id,
        backref="parents",
    )

    @property
    def report_json(self) -> Dict:
        return dict(
            id=self.id,
            task_id=self.task_id,
            # from database.mixins.TaskIDMixin
            task_status=self.task_status,
            package=self.package,
            version=self.version,
            status=self.status,
            release_date=self.release_date,
            scoring_date=self.scoring_date,
            top_score=self.top_score,
            npmsio_score=self.npmsio_score,
            directVulnsCritical_score=self.directVulnsCritical_score,
            directVulnsHigh_score=self.directVulnsHigh_score,
            directVulnsMedium_score=self.directVulnsMedium_score,
            directVulnsLow_score=self.directVulnsLow_score,
            indirectVulnsCritical_score=self.indirectVulnsCritical_score,
            indirectVulnsHigh_score=self.indirectVulnsHigh_score,
            indirectVulnsMedium_score=self.indirectVulnsMedium_score,
            indirectVulnsLow_score=self.indirectVulnsLow_score,
            authors=self.authors,
            contributors=self.contributors,
            immediate_deps=self.immediate_deps,
            all_deps=self.all_deps,
        )

    def json_with_dependencies(self, depth: int = 1) -> Dict:
        return {
            "dependencies": [
                rep.json_with_dependencies(depth - 1) for rep in self.dependencies
            ]
            if depth > 0
            else [],
            **self.report_json,
        }

    def json_with_parents(self, depth: int = 1) -> Dict:
        return {
            "parents": [rep.json_with_parents(depth - 1) for rep in self.parents]
            if depth > 0
            else [],
            **self.report_json,
        }


class PackageLatestReport(db.Model):
    __tablename__ = "latest_reports"

    id = Column("id", Integer, primary_key=True)

    package = Column(String(200))
    version = Column(String(200))
    status = Column(String(200))
    release_date = Column(DateTime)
    scoring_date = Column(DateTime)
    top_score = Column(Integer)
    npmsio_score = Column(Float)
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

    # this relationship is used for persistence
    dependencies = relationship(
        "PackageLatestReport",
        secondary=Dependency.__table__,
        primaryjoin=id == Dependency.__table__.c.depends_on_id,
        secondaryjoin=id == Dependency.__table__.c.used_by_id,
        backref="parents",
    )

    def json_with_dependencies(self, depth=1):
        return dict(
            id=self.id,
            package=self.package,
            version=self.version,
            status=self.status,
            release_date=self.release_date,
            scoring_date=self.scoring_date,
            top_score=self.top_score,
            npmsio_score=self.npmsio_score,
            directVulnsCritical_score=self.directVulnsCritical_score,
            directVulnsHigh_score=self.directVulnsHigh_score,
            directVulnsMedium_score=self.directVulnsMedium_score,
            directVulnsLow_score=self.directVulnsLow_score,
            indirectVulnsCritical_score=self.indirectVulnsCritical_score,
            indirectVulnsHigh_score=self.indirectVulnsHigh_score,
            indirectVulnsMedium_score=self.indirectVulnsMedium_score,
            indirectVulnsLow_score=self.indirectVulnsLow_score,
            authors=self.authors,
            contributors=self.contributors,
            immediate_deps=self.immediate_deps,
            all_deps=self.all_deps,
            dependencies=[
                rep.json_with_dependencies(depth - 1) for rep in self.dependencies
            ]
            if depth > 0
            else [],
        )

    def json_with_parents(self, depth=1):
        return dict(
            id=self.id,
            package=self.package,
            version=self.version,
            status=self.status,
            release_date=self.release_date,
            scoring_date=self.scoring_date,
            top_score=self.top_score,
            npmsio_score=self.npms_io_score,
            directVulnsCritical_score=self.directVulnsCritical_score,
            directVulnsHigh_score=self.directVulnsHigh_score,
            directVulnsMedium_score=self.directVulnsMedium_score,
            directVulnsLow_score=self.directVulnsLow_score,
            indirectVulnsCritical_score=self.indirectVulnsCritical_score,
            indirectVulnsHigh_score=self.indirectVulnsHigh_score,
            indirectVulnsMedium_score=self.indirectVulnsMedium_score,
            indirectVulnsLow_score=self.indirectVulnsLow_score,
            authors=self.authors,
            contributors=self.contributors,
            immediate_deps=self.immediate_deps,
            all_deps=self.all_deps,
            parents=[rep.json_with_parents(depth - 1) for rep in self.parents]
            if depth > 0
            else [],
        )


class CeleryTasks(db.Model):
    __tablename__ = "celery_taskmeta"

    id = Column("id", Integer, primary_key=True)

    task_id = Column(String(155))
    status = Column(String(50))
    date_done = Column(DateTime)
    name = Column(String(155))


def get_package_report(package, version=None):
    if None == version:
        # TODO order-by is hard with semver. Think about splitting out versions
        no_version_query = db.session.query(PackageReport).filter(
            PackageReport.package == package
        )
        log.debug(f"Query is {no_version_query}")
        for rep in no_version_query:
            return rep
    else:
        for rep in db.session.query(PackageReport).filter(
            PackageReport.package == package, PackageReport.version == version
        ):
            return rep
    return None


def get_most_recently_scored_package_report(
    package_name: str,
    package_version: Optional[str] = None,
    scored_after: Optional[datetime] = None,
) -> Optional[PackageReport]:
    "Get the most recently scored PackageReport with package_name, optional package_version, and optionally scored_after the scored_after datetime or None"
    query = db.session.query(PackageReport).filter_by(package=package_name)
    if package_version is not None:
        query = query.filter_by(version=package_version)
    if scored_after is not None:
        query = query.filter(PackageReport.scoring_date >= scored_after)
    log.debug(f"Query is {query}")
    return query.order_by(PackageReport.scoring_date.desc()).limit(1).one_or_none()


def get_placeholder_entry(
    package_name: str, package_version: str
) -> Optional[PackageReport]:
    "Get the placeholder entry, if it exists"
    query = db.session.query(PackageReport).filter_by(package=package_name)
    query = query.filter_by(version=package_version)
    query = query.filter(PackageReport.scoring_date == None)
    log.debug(f"Query is {query}")
    return query.one_or_none()


def get_most_recently_inserted_package_from_name_and_version(
    package_name: str,
    package_version: Optional[str] = None,
    inserted_after: Optional[datetime] = None,
):
    query = db.session.query(PackageVersion).filter_by(name=package_name)
    if package_version is not None:
        query = query.filter_by(version=package_version)
    if inserted_after is not None:
        query = query.filter(PackageVersion.inserted_at >= inserted_after)
    return query.order_by(PackageVersion.inserted_at.desc()).limit(1).one_or_none()


def get_packages_by_ids(package_ids: List[int]) -> List[PackageVersion]:
    return (
        db.session.query(PackageVersion)
        .filter(PackageVersion.id.in_(package_ids))
        .all()
    )


def get_graph_by_id(graph_id: int) -> PackageGraph:
    return db.session.query(PackageGraph).filter_by(id=graph_id).one()


def get_networkx_graph_and_nodes(
    graph: PackageGraph,
) -> Tuple[nx.DiGraph, List[PackageVersion]]:
    graph_links: List[PackageLink] = get_graph_links(graph)
    graph_links_by_package_id = [
        (link.parent_package_id, link.child_package_id) for link in graph_links
    ]
    graph_nodes: List[PackageVersion] = get_packages_by_ids(
        set([pid for link in graph_links_by_package_id for pid in link])
    )
    return (
        db_graph_and_links_to_nx_graph(graph, graph_links_by_package_id, graph_nodes),
        graph_nodes,
    )


def get_labelled_graphviz_graph(graph_id: int) -> str:
    graph: PackageGraph = get_graph_by_id(graph_id)
    log.debug(graph.root_package_version_id)
    if graph.root_package_version_id is not None:
        root = get_packages_by_ids([graph.root_package_version_id])[0]
        log.debug(f"root {root.name}@{root.version}")
    return str(graph_to_dot(get_networkx_graph_and_nodes(graph)[0]))


def db_graph_and_links_to_nx_graph(
    graph: PackageGraph, links: List[Tuple[int, int]], nodes: List[PackageVersion]
) -> nx.DiGraph:
    # TODO: de-dup with depobs.scanner.graph_util.npm_packages_to_networkx_digraph
    g = nx.DiGraph()
    for node in nodes:
        g.add_node(node.id, label=f"{node.name}@{node.version}")

    for link in links:
        g.add_edge(link[0], link[1])
    return g


def graph_to_dot(g: nx.DiGraph) -> pydot.Graph:
    # TODO: de-dup with depobs.scanner.pipelines.{crate,dep_graph}
    pdot: pydot.Graph = to_pydot(g)
    pdot.set("rankdir", "LR")
    return pdot


def get_latest_graph_including_package_as_parent(
    package: PackageVersion,
) -> Optional[PackageGraph]:
    """
    For a PackageVersion finds the newest package link where the
    package is a parent and returns newest package graph using that link
    """
    link = (
        db.session.query(PackageLink)
        .filter(PackageLink.parent_package_id == package.id)
        .order_by(PackageLink.inserted_at.desc())
        .limit(1)
        .one_or_none()
    )
    if link is None:
        log.info(f"{package.name} {package.version} has no children")
        return None
    graph_query = (
        db.session.query(PackageGraph)
        .filter(PackageGraph.link_ids.contains([link.id]))
        .order_by(PackageGraph.inserted_at.desc())
        .limit(1)
    )
    log.debug(f"graph_query is {graph_query}")
    return graph_query.one_or_none()


def get_graph_links(graph: PackageGraph) -> List[PackageLink]:
    return (
        db.session.query(PackageLink)
        .filter(PackageLink.id.in_([lid[0] for lid in graph.link_ids]))
        .all()
    )


def get_package_from_id(id: int) -> Optional[PackageVersion]:
    package_version = (
        db.session.query(PackageVersion).filter(PackageVersion.id == id).one_or_none()
    )
    if package_version is None:
        log.info(f"no package found for get_package_id {id}")
    return package_version


def get_child_package_ids_from_parent_package_id(
    links: List[PackageLink], subject: PackageVersion
) -> List[int]:
    return [
        link.child_package_id for link in links if link.parent_package_id == subject.id
    ]


def get_vulnerabilities_report(package: str, version: str) -> Dict:
    vulns = []
    for package_name, version, severity, url, title in get_vulnerabilities(
        package, version
    ):
        vulns.append(dict(severity=severity, url=url, title=title))
    return dict(package=package, version=version, vulnerabilities=vulns)


def get_npms_io_score(package: str, version: str):
    return db.session.query(NPMSIOScore.score).filter_by(
        package_name=package, package_version=version
    )


def get_NPMRegistryEntry(package: str, version: str):
    return db.session.query(NPMRegistryEntry).filter_by(
        package_name=package, package_version=version
    )


def get_maintainers_contributors(package: str, version: str):
    return db.session.query(
        NPMRegistryEntry.maintainers, NPMRegistryEntry.contributors
    ).filter_by(package_name=package, package_version=version)


def get_npm_registry_data(package: str, version: str):
    return db.session.query(
        NPMRegistryEntry.published_at,
        NPMRegistryEntry.maintainers,
        NPMRegistryEntry.contributors,
    ).filter_by(package_name=package, package_version=version)


def get_vulnerability_counts(package: str, version: str):
    return (
        db.session.query(
            Advisory.package_name,
            PackageVersion.version,
            Advisory.severity,
            func.count(Advisory.severity),
        )
        .filter_by(package_name=package)
        .filter(PackageVersion.version == version)
        .filter(Advisory.package_name == PackageVersion.name)
        .group_by(Advisory.package_name, PackageVersion.version, Advisory.severity)
    )


def get_vulnerabilities(package: str, version: str):
    return (
        db.session.query(
            Advisory.package_name,
            PackageVersion.version,
            Advisory.severity,
            Advisory.url,
            Advisory.title,
        )
        .filter_by(package_name=package)
        .filter(PackageVersion.version == version)
        .filter(Advisory.package_name == PackageVersion.name)
    )


def get_statistics():
    pkg_version_count = (
        db.session.query(PackageVersion.name, PackageVersion.version,)
        .distinct()
        .count()
    )
    advisories_count = db.session.query(Advisory.id).count()
    reports_count = db.session.query(PackageReport.id).count()

    tasks_results = (
        db.session.query(CeleryTasks.status, func.count(CeleryTasks.id))
        .group_by(CeleryTasks.status)
        .all()
    )
    tasks_count = dict()
    for k, v in tasks_results:
        tasks_count[k.lower()] = v

    return dict(
        package_versions=pkg_version_count,
        advisories=advisories_count,
        reports=reports_count,
        tasks=tasks_count,
    )


def insert_package_report_placeholder_or_update_task_id(
    package_name: str, package_version: str, task_id: str
) -> PackageReport:
    # if the package version was scored at any time
    pr: Optional[PackageReport] = get_most_recently_scored_package_report(
        package_name, package_version
    )
    if pr is not None:
        # update its scan task id
        pr.task_id = task_id
    else:
        pr = PackageReport()
        pr.package = package_name
        pr.version = package_version
        pr.status = "scanning"
        pr.task_id = task_id
    store_package_report(pr)
    return pr


def store_package_report(pr) -> None:
    db.session.add(pr)
    db.session.commit()


def store_package_reports(prs: List[PackageReport]) -> None:
    db.session.add_all(prs)
    db.session.commit()


def insert_npmsio_score(npmsio_score: Dict[str, Any]) -> None:
    return insert_npmsio_data(db.session, [npmsio_score])


def insert_npm_registry_entry(npm_registry_entry: Dict[str, Any]) -> None:
    return insert_npm_registry_data(db.session, [npm_registry_entry])


VIEWS: Dict[str, str] = {
    "latest_reports": """
CREATE OR REPLACE VIEW latest_reports AS
SELECT * From (
SELECT r.*, row_number() OVER (PARTITION BY package, version ORDER BY scoring_date desc) AS rn
       FROM reports r
     ) r2
WHERE r2.rn = 1
    """
}


def create_views(engine):
    connection = engine.connect()
    log.info(f"creating views if they don't exist: {list(VIEWS.keys())}")
    for view_command in VIEWS.values():
        _ = connection.execute(view_command)
    connection.close()


def create_tables_and_views(app):
    with app.app_context():
        scanner_tables = scanner_schema_declarative_base.metadata.tables
        log.info(
            f"creating scanner tables if they don't exist: {list(scanner_tables.keys())}"
        )
        scanner_schema_declarative_base.metadata.create_all(bind=db.engine,)
        non_view_table_names = [
            table_name
            for table_name in db.Model.metadata.tables
            if table_name not in VIEWS.keys()
        ]
        log.info(f"creating tables if they don't exist: {non_view_table_names}")
        db.Model.metadata.create_all(
            bind=db.engine,
            tables=[
                db.Model.metadata.tables[table_name]
                for table_name in non_view_table_names
            ],
        )
        create_views(db.engine)
