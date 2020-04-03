# Placeholder for model code

import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import networkx as nx
from networkx.drawing.nx_pydot import to_pydot
import pydot
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, \
     ForeignKey, event, select
from sqlalchemy.orm import scoped_session, sessionmaker, backref, relation, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Table
from sqlalchemy import func, tuple_
from sqlalchemy.orm import aliased, Load, load_only

from fpr.db.schema import Advisory, NPMRegistryEntry, NPMSIOScore, PackageGraph, PackageLink, PackageVersion
from depobs.database.mixins import TaskIDMixin


DATABASE_URI = os.environ.get('DATABASE_URI', 'postgresql+psycopg2://postgres:postgres@localhost/dependency_observatory')

engine = create_engine(DATABASE_URI)

db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))

Model = declarative_base()
View_only = declarative_base()
# Model.query = db_session.query_property()

dependency = Table(
    'package_dependencies', Model.metadata,
    Column('depends_on_id', Integer, ForeignKey('reports.id'), primary_key=True),
    Column('used_by_id', Integer, ForeignKey('reports.id'), primary_key=True)
)

class PackageReport(TaskIDMixin, Model):
    __tablename__ = 'reports'

    id = Column('id', Integer, primary_key=True)

    package = Column(String(200))
    version = Column(String(200))
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
    dependencies = relationship("PackageReport",
                           secondary=dependency,
                           primaryjoin=id==dependency.c.depends_on_id,
                           secondaryjoin=id==dependency.c.used_by_id,
                           backref="parents"
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
            authors = self.authors,
            contributors = self.contributors,
            immediate_deps = self.immediate_deps,
            all_deps = self.all_deps,
        )

    def json_with_dependencies(self, depth: int = 1) -> Dict:
        return {'dependencies': [rep.json_with_dependencies(depth - 1) for rep in self.dependencies] if depth > 0 else [], **self.report_json}

    def json_with_parents(self, depth: int = 1) -> Dict:
        return {'parents': [rep.json_with_parents(depth - 1) for rep in self.parents] if depth > 0 else [], **self.report_json}

class PackageLatestReport(View_only):
    __tablename__ = 'latest_reports'

    id = Column('id', Integer, primary_key=True)

    package = Column(String(200))
    version = Column(String(200))
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
    dependencies = relationship("PackageLatestReport",
                           secondary=dependency,
                           primaryjoin=id==dependency.c.depends_on_id,
                           secondaryjoin=id==dependency.c.used_by_id,
                           backref="parents"
    )

    def json_with_dependencies(self, depth = 1):
        return dict(
            id=self.id,
            package=self.package,
            version=self.version,
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
            authors = self.authors,
            contributors = self.contributors,
            immediate_deps = self.immediate_deps,
            all_deps = self.all_deps,
            dependencies = [rep.json_with_dependencies(depth - 1) for rep in self.dependencies] if depth > 0 else []
        )

    def json_with_parents(self, depth = 1):
        return dict(
            id=self.id,
            package=self.package,
            version=self.version,
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
            authors = self.authors,
            contributors = self.contributors,
            immediate_deps = self.immediate_deps,
            all_deps = self.all_deps,
            parents = [rep.json_with_parents(depth - 1) for rep in self.parents] if depth > 0 else []
        )

def get_package_report(package, version = None):
    if None == version:
        #TODO order-by is hard with semver. Think about splitting out versions
        no_version_query = db_session.query(PackageReport).filter(PackageReport.package==package)
        print(f"Query is {no_version_query}")
        for rep in no_version_query:
            return rep
    else:
        for rep in db_session.query(PackageReport).filter(PackageReport.package==package, PackageReport.version==version):
            return rep
    return None


def get_most_recently_scored_package_report(package_name: str, package_version: Optional[str]=None, scored_after: Optional[datetime]=None) -> Optional[PackageReport]:
    "Get the most recently scored PackageReport with package_name, optional package_version, and optionally scored_after the scored_after datetime or None"
    query = db_session.query(PackageReport).filter_by(package=package_name)
    if package_version is not None:
        query = query.filter_by(version=package_version)
    if scored_after is not None:
        query = query.filter(PackageReport.scoring_date >= scored_after)
    print(f"Query is {query}")
    return query.order_by(PackageReport.scoring_date.desc()).limit(1).one_or_none()


def get_placeholder_entry(package_name: str, package_version: str) -> Optional[PackageReport]:
    "Get the placeholder entry, if it exists"
    query = db_session.query(PackageReport).filter_by(package=package_name)
    query = query.filter_by(version=package_version)
    query = query.filter(PackageReport.scoring_date == None)
    print(f"Query is {query}")
    return query.one_or_none()


def get_most_recently_inserted_package_from_name_and_version(
        package_name: str,
        package_version: Optional[str]=None,
        inserted_after: Optional[datetime]=None
):
    query = db_session.query(PackageVersion).filter_by(name=package_name)
    if package_version is not None:
        query = query.filter_by(version=package_version)
    if inserted_after is not None:
        query = query.filter(PackageVersion.inserted_at >= inserted_after)
    return query.order_by(PackageVersion.inserted_at.desc()).limit(1).one_or_none()


def get_packages_by_ids(package_ids: List[int]) -> List[PackageVersion]:
    return db_session.query(PackageVersion).filter(PackageVersion.id.in_(package_ids)).all()


def get_graph_by_id(graph_id: int) -> PackageGraph:
    return db_session.query(PackageGraph).filter_by(id=graph_id).one()


def get_networkx_graph_and_nodes(graph: PackageGraph) -> Tuple[nx.DiGraph, List[PackageVersion]]:
    graph_links: List[PackageLink] = get_graph_links(graph)
    graph_links_by_package_id = [(link.parent_package_id, link.child_package_id) for link in graph_links]
    graph_nodes: List[PackageVersion] = get_packages_by_ids(set([pid for link in graph_links_by_package_id for pid in link]))
    return db_graph_and_links_to_nx_graph(graph, graph_links_by_package_id, graph_nodes), graph_nodes


def get_labelled_graphviz_graph(graph_id: int) -> str:
    graph: PackageGraph = get_graph_by_id(graph_id)
    print(graph.root_package_version_id)
    if graph.root_package_version_id is not None:
        root = get_packages_by_ids([graph.root_package_version_id])[0]
        print(f"root {root.name}@{root.version}")
    return str(graph_to_dot(get_networkx_graph_and_nodes(graph)[0]))


def db_graph_and_links_to_nx_graph(graph: PackageGraph, links: List[Tuple[int, int]], nodes: List[PackageVersion]) -> nx.DiGraph:
    # TODO: de-dup with fpr.graph_util.npm_packages_to_networkx_digraph
    g = nx.DiGraph()
    for node in nodes:
        g.add_node(node.id, label=f"{node.name}@{node.version}")

    for link in links:
        g.add_edge(link[0], link[1])
    return g


def graph_to_dot(g: nx.DiGraph) -> pydot.Graph:
    # TODO: de-dup with fpr.pipelines.{crate,dep_graph}
    pdot: pydot.Graph = to_pydot(g)
    pdot.set("rankdir", "LR")
    return pdot


def get_latest_graph_including_package_as_parent(package: PackageVersion) -> Optional[PackageGraph]:
    """
    For a PackageVersion finds the newest package link where the
    package is a parent and returns newest package graph using that link
    """
    link = db_session.query(PackageLink).filter(PackageLink.parent_package_id == package.id).order_by(PackageLink.inserted_at.desc()).limit(1).one_or_none()
    if link is None:
        print(f"{package.name} {package.version} has no children")
        return None
    graph_query = db_session.query(PackageGraph).filter(PackageGraph.link_ids.contains([link.id])).order_by(PackageGraph.inserted_at.desc()).limit(1)
    print(f"graph_query is {graph_query}")
    return graph_query.one_or_none()


def get_graph_links(graph: PackageGraph) -> List[PackageLink]:
    return db_session.query(PackageLink).filter(PackageLink.id.in_([lid[0] for lid in graph.link_ids])).all()


def get_package_from_id(id: int) -> Optional[PackageVersion]:
    package_version = db_session.query(PackageVersion).filter(PackageVersion.id == id).one_or_none()
    if package_version is None:
        print(f"no package found for get_package_id {id}")
    return package_version


def get_child_package_ids_from_parent_package_id(links: List[PackageLink], subject: PackageVersion) -> List[int]:
    return [
        link.child_package_id for link in links if link.parent_package_id == subject.id
    ]


def get_ordered_package_deps_and_reports(links: List[PackageLink], name: str, version: str) -> Tuple[List[Tuple[str, str]], List[PackageReport]]:
    deps = []
    incomplete = False

    subject = get_most_recently_inserted_package_from_name_and_version(name, version)
    if subject is None:
        print(f"subject dep {name} {version} not found returning empty deps and reports")
        return [], []

    print(f"subject is {subject.name} {subject.version} {subject.id}")

    dependency_ids = get_child_package_ids_from_parent_package_id(links, subject)
    print(f"found dependency ids for {subject.name} {subject.version}: {dependency_ids}")
    maybe_dependencies = [get_package_from_id(dependency_id) for dependency_id in dependency_ids]
    dependencies = [dep for dep in maybe_dependencies if dep is not None]
    reports = []
    for dependency in dependencies:
        print(f"dependency {dependency.id} {dependency.name} {dependency.version}")
        report = get_package_report(dependency.name, dependency.version)
        if None == report:
            incomplete = True
            deps.append((dependency.name, dependency.version))
        else:
            reports.append(report)
    if incomplete:
        print(f"dependencies for {name}, {version} incomplete, re-adding to the queue")
        deps.append((name, version))
    else:
        print(f"dependencies complete for {name}, {version} adding to the graph")
        pr = PackageReport()
        pr.package = name
        pr.version = version
        pr.top_score = 0
        pr.npmsio_score = 0
        pr.directVulnsCritical_score = 0
        pr.directVulnsHigh_score = 0
        pr.directVulnsMedium_score = 0
        pr.directVulnsLow_score = 0
        pr.indirectVulnsCritical_score = 0
        pr.indirectVulnsHigh_score = 0
        pr.indirectVulnsMedium_score = 0
        pr.indirectVulnsLow_score = 0
        pr.authors = 0
        pr.contributors = 0
        pr.immediate_deps = 0
        pr.all_deps = 0

        for report in reports:
            pr.dependencies.append(report)
        db_session.add(pr)
        db_session.commit()
    return deps, reports

def get_vulnerabilities_report(package: str, version: str) -> Dict:
    vulns = []
    for package_name, version, severity, url, title in get_vulnerabilities(package, version):
        vulns.append(dict(
            severity=severity,
            url=url,
            title=title
            ))
    return dict(
        package=package,
        version=version,
        vulnerabilities=vulns
        )

def get_npms_io_score(package: str, version: str):
    return db_session.query(NPMSIOScore.score).filter_by(package_name=package, package_version=version)

def get_NPMRegistryEntry(package: str, version: str):
    return db_session.query(NPMRegistryEntry).filter_by(package_name=package, package_version=version)

def get_maintainers_contributors(package: str, version: str):
    return db_session.query(NPMRegistryEntry.maintainers, NPMRegistryEntry.contributors).filter_by(package_name=package, package_version=version)

def get_npm_registry_data(package: str, version: str):
    return db_session.query(NPMRegistryEntry.published_at, NPMRegistryEntry.maintainers, NPMRegistryEntry.contributors).filter_by(package_name=package, package_version=version)

def get_direct_dependencies(package: str, version: str):
    palias = aliased(PackageVersion)
    calias = aliased(PackageVersion)
    return db_session.query(calias.name, calias.version
    ).filter(PackageLink.parent_package_id==palias.id
    ).filter(palias.name==package
    ).filter(palias.version==version
    ).filter(PackageLink.child_package_id==calias.id)

def get_vulnerability_counts(package: str, version: str):
    return db_session.query(Advisory.package_name, PackageVersion.version, Advisory.severity,
        func.count(Advisory.severity)
    ).filter_by(package_name=package
    ).filter(PackageVersion.version==version
    ).filter(Advisory.package_name==PackageVersion.name
    ).group_by(Advisory.package_name, PackageVersion.version, Advisory.severity)

def get_vulnerabilities(package: str, version: str):
    return db_session.query(Advisory.package_name, PackageVersion.version, Advisory.severity, Advisory.url, Advisory.title
    ).filter_by(package_name=package
    ).filter(PackageVersion.version==version
    ).filter(Advisory.package_name==PackageVersion.name)

def get_direct_dependency_reports(package: str, version: str):
    palias = aliased(PackageVersion)
    calias = aliased(PackageVersion)
    return db_session.query(calias.name, calias.version, PackageLatestReport.scoring_date, PackageLatestReport.top_score, PackageLatestReport.all_deps,
        PackageLatestReport.directVulnsCritical_score, PackageLatestReport.directVulnsHigh_score, PackageLatestReport.directVulnsMedium_score, PackageLatestReport.directVulnsLow_score,
        PackageLatestReport.indirectVulnsCritical_score, PackageLatestReport.indirectVulnsHigh_score, PackageLatestReport.indirectVulnsMedium_score, PackageLatestReport.indirectVulnsLow_score
    ).filter(PackageLink.parent_package_id==palias.id
    ).filter(palias.name==package
    ).filter(palias.version==version
    ).filter(PackageLink.child_package_id==calias.id
    ).filter(PackageLatestReport.package==calias.name
    ).filter(PackageLatestReport.version==calias.version)


def insert_package_report_placeholder_or_update_task_id(package_name: str, package_version: str, task_id: str) -> PackageReport:
    # if the package version was scored at any time
    pr: Optional[PackageReport] = get_most_recently_scored_package_report(package_name, package_version)
    if pr is not None:
        # update its scan task id
        pr.task_id = task_id
    else:
        pr = PackageReport()
        pr.package = package_name
        pr.version = package_version
        pr.task_id = task_id
    store_package_report(pr)
    return pr


def store_package_report(pr) -> None:
    db_session.add(pr)
    db_session.commit()


def store_package_reports(prs: List[PackageReport]) -> None:
    db_session.add_all(prs)
    db_session.commit()


VIEWS: List[str] = [
    """
CREATE OR REPLACE VIEW latest_reports AS
SELECT * From (
SELECT r.*, row_number() OVER (PARTITION BY package, version ORDER BY scoring_date desc) AS rn
       FROM reports r
     ) r2
WHERE r2.rn = 1
    """
]


def create_views(engine):
    connection = engine.connect()
    for view_command in VIEWS:
        _ = connection.execute(view_command)
    connection.close()


def init_db():
    Model.metadata.create_all(bind=engine)
    create_views(engine)
