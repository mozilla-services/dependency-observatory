from datetime import datetime
from functools import cached_property
import logging
from typing import Any, Dict, List, Optional, Set, Tuple, Iterable

import flask
from flask_sqlalchemy import SQLAlchemy
import networkx as nx
import sqlalchemy
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    LargeBinary,
    Numeric,
    Index,
    Integer,
    Sequence,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import backref, deferred, relationship
from sqlalchemy.sql import func, expression
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import DateTime
from sqlalchemy.schema import Table
from sqlalchemy import func

from depobs.database.mixins import TaskIDMixin


log = logging.getLogger(__name__)


db: SQLAlchemy = SQLAlchemy()

# define type aliases to make ints distinguishable in type annotations
PackageLinkID = int
PackageVersionID = int


class utcnow(expression.FunctionElement):
    type = DateTime()


@compiles(utcnow, "postgresql")
def pg_utcnow(element: Any, compiler: Any, **kw: Dict) -> str:
    return "TIMEZONE('utc', CURRENT_TIMESTAMP)"


# TODO: harmonize with stuff defined in models/languages
lang_enum = ENUM("node", "rust", "python", name="language_enum")
package_manager_enum = ENUM("npm", "yarn", name="package_manager_enum")


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
    dependencies: sqlalchemy.orm.RelationshipProperty = relationship(
        "PackageReport",
        secondary=Dependency.__table__,
        primaryjoin=id == Dependency.__table__.c.depends_on_id,
        secondaryjoin=id == Dependency.__table__.c.used_by_id,
        backref="parents",
    )

    @staticmethod
    def get_letter_grade(score: int) -> str:
        if score >= 80:
            return "A"
        elif score >= 60:
            return "B"
        elif score >= 40:
            return "C"
        elif score >= 20:
            return "D"
        else:
            return "E"

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


class PackageVersion(db.Model):
    __tablename__ = "package_versions"

    id = Column(Integer, Sequence("package_version_id_seq"), primary_key=True)

    # has a name, resolved version, and language
    name = Column(String, nullable=False, primary_key=True)
    version = Column(String, nullable=False, primary_key=True)
    language = Column(lang_enum, nullable=False, primary_key=True)

    # has an optional distribution URL
    url = deferred(Column(String, nullable=True))

    # has an optional source repository and commit
    repo_url = deferred(Column(String, nullable=True))
    repo_commit = deferred(Column(LargeBinary, nullable=True))

    # track when it was inserted and changed
    inserted_at = deferred(Column(DateTime(timezone=False), server_default=utcnow()))
    updated_at = deferred(Column(DateTime(timezone=False), onupdate=utcnow()))

    @declared_attr
    def __table_args__(cls) -> Iterable[Index]:
        return (
            Index(
                f"{cls.__tablename__}_unique_idx",
                "name",
                "version",
                "language",
                unique=True,
            ),
            Index(
                f"{cls.__tablename__}_inserted_idx",
                "inserted_at",
                expression.desc(cls.inserted_at),
            ),
        )


class PackageLink(db.Model):
    __tablename__ = "package_links"

    id = Column(
        Integer, Sequence("package_version_link_id_seq"), primary_key=True, unique=True
    )

    child_package_id = Column(
        Integer, primary_key=True, nullable=False  # ForeignKey("package_versions.id"),
    )
    parent_package_id = Column(
        Integer, primary_key=True, nullable=False  # ForeignKey("package_versions.id"),
    )

    # track when it was inserted
    inserted_at = deferred(Column(DateTime(timezone=False), server_default=utcnow()))

    @declared_attr
    def __table_args__(cls) -> Iterable[Index]:
        return (
            # ForeignKeyConstraint(
            #     ["child_package_id"],
            #     [
            #         "package_versions.id",
            #     ],
            # ),
            # ForeignKeyConstraint(
            #     ["parent_package_id"],
            #     [
            #         "package_versions.id",
            #     ],
            # ),
            Index(
                f"{cls.__tablename__}_unique_idx",
                "child_package_id",
                "parent_package_id",
                unique=True,
            ),
            Index(
                f"{cls.__tablename__}_inserted_idx",
                "inserted_at",
                expression.desc(cls.inserted_at),
            ),
        )


class PackageGraph(db.Model):
    __tablename__ = "package_graphs"

    id = Column(Integer, Sequence("package_graphs_id_seq"), primary_key=True)

    # package version we resolved
    root_package_version_id = Column(
        Integer, nullable=False, primary_key=True  # ForeignKey("package_versions.id"),
    )

    # link ids of direct and transitive deps
    link_ids = deferred(Column(ARRAY(Integer)))  # ForeignKey("package_links.id"))

    # what resolved it
    package_manager = deferred(Column(package_manager_enum, nullable=True))
    package_manager_version = deferred(Column(String, nullable=True))

    # track when it was inserted
    inserted_at = deferred(Column(DateTime(timezone=False), server_default=utcnow()))

    @cached_property
    def package_links_by_id(
        self,
    ) -> Dict[PackageLinkID, Tuple[PackageVersionID, PackageVersionID]]:
        return {
            link.id: (link.parent_package_id, link.child_package_id)
            for link in db.session.query(PackageLink).filter(
                PackageLink.id.in_([lid[0] for lid in self.link_ids])
            )
        }

    @cached_property
    def distinct_package_ids(self) -> Set[PackageVersionID]:
        return set(
            [
                package_id
                for link in self.package_links_by_id.values()
                for package_id in link
            ]
        )

    @cached_property
    def distinct_package_versions_by_id(self) -> Dict[PackageVersionID, PackageVersion]:
        return {
            package_version.id: package_version
            for package_version in get_packages_by_ids(self.distinct_package_ids)
        }

    def get_npm_registry_data_by_package_version_id(
        self,
    ) -> Dict[PackageVersionID, Optional["NPMRegistryEntry"]]:
        # TODO: fetch all entries in one request
        # want latest entry data matching package name and version
        # e.g. GROUP BY name, version ORDER BY inserted_at or updated_at DESC
        # not cached since it can change as more entries fetched or updated
        return {
            package_version.id: get_npm_registry_data(
                package_version.name, package_version.version
            ).first()
            for package_version in self.distinct_package_versions_by_id.values()
        }

    def get_npmsio_scores_by_package_version_id(
        self,
    ) -> Dict[PackageVersionID, Optional[float]]:
        # TODO: fetch all scores in one request
        # not cached since it can change as scores fetched or updated
        tmp = {
            package_version.id: get_npms_io_score(
                package_version.name, package_version.version
            ).first()
            for package_version in self.distinct_package_versions_by_id.values()
        }
        return {
            # TODO: figure out if we cant get one row or None back
            pv_id: score[0] if isinstance(score, tuple) else None
            for pv_id, score in tmp.items()
        }

    def get_advisories_by_package_version_id(
        self,
    ) -> Dict[PackageVersionID, List["Advisory"]]:
        # TOOD: fetch all with one DB call
        return {
            package_version.id: get_advisories_by_package_versions(
                [package_version]
            ).all()
            for package_version in self.distinct_package_versions_by_id.values()
        }

    @declared_attr
    def __table_args__(cls) -> Iterable[Index]:
        return (
            Index(
                f"{cls.__tablename__}_root_package_id_idx", "root_package_version_id"
            ),
            Index(
                f"{cls.__tablename__}_link_ids_idx", "link_ids", postgresql_using="gin"
            ),
            Index(f"{cls.__tablename__}_package_manager_idx", "package_manager"),
            Index(
                f"{cls.__tablename__}_package_manager_version_idx",
                "package_manager_version",
            ),
            Index(
                f"{cls.__tablename__}_inserted_idx",
                "inserted_at",
                expression.desc(cls.inserted_at),
            ),
        )


class Advisory(db.Model):
    __tablename__ = "advisories"

    id = Column(Integer, Sequence("advisories_id_seq"), primary_key=True, unique=True)
    language = Column(lang_enum, nullable=False, primary_key=True)

    # has optional name, npm advisory id, and url
    package_name = Column(
        String, nullable=True
    )  # included in case vulnerable_package_version_ids is empty
    npm_advisory_id = Column(Integer, nullable=True)
    url = Column(String, nullable=True)

    severity = Column(String, nullable=True)
    cwe = Column(Integer, nullable=True)
    cves = deferred(Column(ARRAY(String), nullable=True))

    exploitability = Column(Integer, nullable=True)
    title = Column(String, nullable=True)

    # vulnerable and patched versions from the advisory as a string
    vulnerable_versions = deferred(Column(String, nullable=True))
    patched_versions = deferred(Column(String, nullable=True))

    # vulnerable package versions from our resolved package versions
    # TODO: validate affected deps. from findings[].paths[] for a few graphs
    vulnerable_package_version_ids = deferred(
        Column(ARRAY(Integer))
    )  # ForeignKey("package_versions.id"))

    # advisory publication info
    created = deferred(Column(DateTime(timezone=False), nullable=True))
    updated = deferred(Column(DateTime(timezone=False), nullable=True))

    # track when it was inserted or last updated in our DB
    inserted_at = deferred(Column(DateTime(timezone=False), server_default=utcnow()))
    updated_at = deferred(Column(DateTime(timezone=False), onupdate=utcnow()))

    @declared_attr
    def __table_args__(cls) -> Iterable[Index]:
        return (
            Index(f"{cls.__tablename__}_language_idx", "language"),
            Index(f"{cls.__tablename__}_pkg_name_idx", "package_name"),
            Index(f"{cls.__tablename__}_npm_advisory_id_idx", "npm_advisory_id"),
            Index(
                f"{cls.__tablename__}_vulnerable_package_version_ids_idx",
                "vulnerable_package_version_ids",
                postgresql_using="gin",
            ),
            Index(
                f"{cls.__tablename__}_inserted_idx",
                "inserted_at",
                expression.desc(cls.inserted_at),
            ),
        )


class NPMSIOScore(db.Model):
    __tablename__ = "npmsio_scores"

    """
    Score of a package version at the analyzed_at time

    many to one with package_versions, so join on package_name and package_version
    and pick an analyzed_at date or compare over time
    """
    # TODO: make sure we aren't truncating data

    id = Column(Integer, Sequence("npmsio_score_id_seq"), primary_key=True)

    package_name = Column(
        String, nullable=False, primary_key=True
    )  # from .collected.metadata.name
    package_version = Column(
        String, nullable=False, primary_key=True
    )  # from .collected.metadata.version
    analyzed_at = Column(
        DateTime(timezone=False), nullable=False, primary_key=True
    )  # from .analyzedAt e.g. "2019-11-27T19:31:42.541Z

    # e.g. https://api.npms.io/v2/package/{package_name} might change if the API changes
    source_url = Column(String, nullable=False)

    # overall score from .score.final on the interval [0, 1]
    score = Column(Numeric, nullable=True)  # from .score.final

    # score components on the interval [0, 1]
    quality = Column(Numeric, nullable=True)  # from .detail.quality
    popularity = Column(Numeric, nullable=True)  # from .detail.popularity
    maintenance = Column(Numeric, nullable=True)  # from .detail.maintenance

    # score subcomponent/detail fields from .evaluation.<component>.<subcomponent>

    # all on the interval [0, 1]
    branding = Column(Numeric, nullable=True)  # from .evaluation.quality.branding
    carefulness = Column(Numeric, nullable=True)  # from .evaluation.quality.carefulness
    health = Column(Numeric, nullable=True)  # from .evaluation.quality.health
    tests = Column(Numeric, nullable=True)  # from .evaluation.quality.tests

    community_interest = Column(
        Integer, nullable=True
    )  # 0+ from .evaluation.popularity.communityInterest
    dependents_count = Column(
        Integer, nullable=True
    )  # 0+ from .evaluation.popularity.dependentsCount
    downloads_count = Column(
        Numeric, nullable=True
    )  # some of these are fractional? from .evaluation.popularity.downloadsCount
    downloads_acceleration = Column(
        Numeric, nullable=True
    )  # signed decimal (+/-) from .evaluation.popularity.downloadsAcceleration

    # all on the interval [0, 1]
    commits_frequency = Column(
        Numeric, nullable=True
    )  # from .evaluation.maintenance.commitsFrequency
    issues_distribution = Column(
        Numeric, nullable=True
    )  # from .evaluation.maintenance.issuesDistribution
    open_issues = Column(
        Numeric, nullable=True
    )  # from .evaluation.maintenance.openIssues
    releases_frequency = Column(
        Numeric, nullable=True
    )  # from .evaluation.maintenance.releasesFrequency

    # TODO: add .collected fields that feed into the score

    # track when it was inserted or last updated in our DB
    inserted_at = deferred(Column(DateTime(timezone=False), server_default=utcnow()))
    updated_at = deferred(Column(DateTime(timezone=False), onupdate=utcnow()))

    @declared_attr
    def __table_args__(cls) -> Iterable[Index]:
        return (
            # TODO: add indexes on interesting score columns?
            Index(
                f"{cls.__tablename__}_unique_idx",
                "package_name",
                "package_version",
                "analyzed_at",
                unique=True,
            ),
            Index(
                f"{cls.__tablename__}_analyzed_idx",
                "analyzed_at",
                expression.desc(cls.analyzed_at),  # type: ignore
            ),
            Index(
                f"{cls.__tablename__}_updated_idx",
                "updated_at",
                expression.desc(cls.updated_at),
            ),
            Index(
                f"{cls.__tablename__}_inserted_idx",
                "inserted_at",
                expression.desc(cls.inserted_at),
            ),
        )


class NPMRegistryEntry(db.Model):
    __tablename__ = "npm_registry_entries"

    """
    package and version info from the npm registry

    many to one with package_versions, so join on package_name and package_version
    and pick or aggregate tarball and shasums
    """
    id = Column(Integer, Sequence("npm_registry_entry_id_seq"), primary_key=True)

    # "The name, version, and dist fields will always be present."
    #
    # https://github.com/npm/registry/blob/master/docs/responses/package-metadata.md#abbreviated-version-object
    #
    # the package name from .versions[<version>].name
    package_name = Column(String, nullable=False, primary_key=True)
    # the version string for this version from .versions[<version>].version
    package_version = Column(String, nullable=False, primary_key=True)

    # https://github.com/npm/registry/blob/master/docs/responses/package-metadata.md#dist
    #
    # from .versions[<version>].dist.shasum e.g. f616eda9d3e4b66b8ca7fca79f695722c5f8e26f
    shasum = deferred(Column(String, nullable=False, primary_key=True))
    # from .versions[<version>].dist.tarball e.g. https://registry.npmjs.org/backoff/-/backoff-2.5.0.tgz
    tarball = deferred(Column(String, nullable=False, primary_key=True))

    # from .versions[<version>].gitHead e.g. '811118fd1f89e9ca4e6b67292b9ef5da6c4f60e9'
    git_head = deferred(Column(String, nullable=True))

    # https://github.com/npm/registry/blob/master/docs/responses/package-metadata.md#repository
    #
    # from .versions[<version>].repository.type e.g. 'git'
    repository_type = deferred(Column(String, nullable=True))
    # from .versions[<version>].repository.url e.g. 'git+https://github.com/MathieuTurcotte/node-backoff.git'
    repository_url = deferred(Column(String, nullable=True))

    # a short description of the package from .versions[<version>].description
    description = deferred(Column(String, nullable=True))

    # url from .versions[<version>].url
    url = deferred(Column(String, nullable=True))

    # the SPDX identifier https://spdx.org/licenses/ of the package's license
    # from .versions[<version>].license
    license_type = deferred(Column(String, nullable=True))
    # link to the license site or file in the repo
    license_url = deferred(Column(String, nullable=True))

    # array of string keywords e.g. ['backoff', 'retry', 'fibonacci', 'exponential']
    keywords = deferred(Column(ARRAY(String)))

    # _hasShrinkwrap: true if this version is known to have a shrinkwrap that
    # must be used to install it; false if this version is known not to have a
    # shrinkwrap. If this field is undefined, the client must determine through
    # other means if a shrinkwrap exists.
    has_shrinkwrap = Column(Boolean, nullable=True)

    # bugs: url e.g.
    # {'url': 'https://github.com/MathieuTurcotte/node-backoff/issues',
    #  'email': 'support@company.example.com'} or maintainer@personal-email.example.com
    bugs_url = deferred(Column(String, nullable=True))
    bugs_email = deferred(Column(String, nullable=True))

    # https://github.com/npm/registry/blob/master/docs/responses/package-metadata.md#human
    #
    # "Historically no validation has been performed on those fields; they are
    # generated by parsing user-provided data in package.json at publication
    # time."
    #
    # TODO: de-dupe humans?
    #
    # author is a human object
    # e.g. {'name': 'Mathieu Turcotte', 'email': 'turcotte.mat@gmail.com'}
    author_name = deferred(Column(String, nullable=True))
    author_email = deferred(Column(String, nullable=True))
    author_url = deferred(Column(String, nullable=True))

    # array of human objects for people with permission to publish this package; not authoritative but informational
    # e.g. [{'name': 'mathieu', 'email': 'turcotte.mat@gmail.com'}]
    maintainers = deferred(Column(JSONB, nullable=True))

    # array of human objects
    contributors = deferred(Column(JSONB, nullable=True))

    # publication info
    # _npmUser: the author object for the npm user who published this version
    # e.g. {'name': 'mathieu', 'email': 'turcotte.mat@gmail.com'}
    # note: no url
    publisher_name = deferred(Column(String, nullable=True))
    publisher_email = deferred(Column(String, nullable=True))
    # _nodeVersion: the version of node used to publish this
    publisher_node_version = deferred(Column(String, nullable=True))
    # _npmVersion: the version of the npm client used to publish this
    publisher_npm_version = deferred(Column(String, nullable=True))

    # published_at .time[<version>] e.g. '2014-05-23T21:21:04.170Z' (not from
    # the version info object)
    #
    # where time: an object mapping versions to the time published, along with created and modified timestamps
    published_at = Column(DateTime(timezone=False), nullable=True)

    # when ANY VERSION of the package was last modified (i.e. how fresh is this entry)
    package_modified_at = Column(DateTime(timezone=False), nullable=True)

    # metadata about how we fetched it

    # where we fetched it from e.g. https://registry.npmjs.org/backoff might change if the API changes
    source_url = Column(String, nullable=False)

    # track when it was inserted or last updated in our DB
    inserted_at = deferred(Column(DateTime(timezone=False), server_default=utcnow()))
    updated_at = deferred(Column(DateTime(timezone=False), onupdate=utcnow()))

    # TODO: add the following fields?
    #
    # main: the package's entry point (e.g., index.js or main.js)
    # deprecated: the deprecation warnings message of this version
    # dependencies: a mapping of other packages this version depends on to the required semver ranges
    # optionalDependencies: an object mapping package names to the required semver ranges of optional dependencies
    # devDependencies: a mapping of package names to the required semver ranges of development dependencies
    # bundleDependencies: an array of dependencies bundled with this version
    # peerDependencies: a mapping of package names to the required semver ranges of peer dependencies
    # bin: a mapping of bin commands to set up for this version
    # directories: an array of directories included by this version
    # engines: the node engines required for this version to run, if specified e.g. {'node': '>= 0.6'}
    # readme: the first 64K of the README data for the most-recently published version of the package
    # readmeFilename: The name of the file from which the readme data was taken.
    #
    # scripts e.g. {'docco': 'docco lib/*.js lib/strategy/* index.js',
    #               'pretest': 'jshint lib/ tests/ examples/ index.js',
    #               'test': 'node_modules/nodeunit/bin/nodeunit tests/'}
    # files e.g. ['index.js', 'lib', 'tests']

    @declared_attr
    def __table_args__(cls) -> Iterable[Index]:
        return (
            Index(
                f"{cls.__tablename__}_unique_idx",
                "package_name",
                "package_version",
                "shasum",
                "tarball",
                unique=True,
            ),
            Index(
                f"{cls.__tablename__}_contributors_idx",
                "contributors",
                postgresql_using="gin",
            ),
            Index(
                f"{cls.__tablename__}_maintainers_idx",
                "maintainers",
                postgresql_using="gin",
            ),
            Index(
                f"{cls.__tablename__}_updated_idx",
                "updated_at",
                expression.desc(cls.updated_at),
            ),
            Index(
                f"{cls.__tablename__}_inserted_idx",
                "inserted_at",
                expression.desc(cls.inserted_at),
            ),
        )


def get_package_report(
    package: str, version: Optional[str] = None
) -> Optional[PackageReport]:
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
) -> Optional[PackageVersion]:
    query = db.session.query(PackageVersion).filter_by(name=package_name)
    if package_version is not None:
        query = query.filter_by(version=package_version)
    if inserted_after is not None:
        query = query.filter(PackageVersion.inserted_at >= inserted_after)
    return query.order_by(PackageVersion.inserted_at.desc()).limit(1).one_or_none()


def get_packages_by_ids(package_ids: Iterable[int]) -> List[PackageVersion]:
    return (
        db.session.query(PackageVersion)
        .filter(PackageVersion.id.in_(package_ids))
        .all()
    )


def get_graph_by_id(graph_id: int) -> PackageGraph:
    return db.session.query(PackageGraph).filter_by(id=graph_id).one()


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


def get_package_from_name_and_version(
    name: str, version: str
) -> Optional[PackageVersion]:
    return (
        db.session.query(PackageVersion)
        .filter_by(name=name, version=version)
        .one_or_none()
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


def get_npms_io_score(package: str, version: str) -> sqlalchemy.orm.query.Query:
    return (
        db.session.query(NPMSIOScore.score)
        .filter_by(package_name=package, package_version=version)
        .order_by(NPMSIOScore.analyzed_at.desc())
    )


def get_package_names_with_missing_npms_io_scores() -> sqlalchemy.orm.query.Query:
    """
    Returns PackageVersion names not in npmsio_scores.

    >>> from depobs.website.do import create_app
    >>> with create_app(dict(INIT_DB=False)).app_context():
    ...     str(get_package_names_with_missing_npms_io_scores())
    ...
    'SELECT DISTINCT package_versions.name AS anon_1 \\nFROM package_versions LEFT OUTER JOIN npmsio_scores ON package_versions.name = npmsio_scores.package_name \\nWHERE npmsio_scores.id IS NULL ORDER BY package_versions.name ASC'
    """
    return (
        db.session.query(sqlalchemy.distinct(PackageVersion.name))
        .outerjoin(NPMSIOScore, PackageVersion.name == NPMSIOScore.package_name)
        .filter(NPMSIOScore.id == None)
        .order_by(PackageVersion.name.asc())
    )


def get_npm_registry_entries_to_scan(
    package_name: str, package_version: Optional[str] = None
) -> sqlalchemy.orm.query.Query:
    query = (
        db.session.query(
            NPMRegistryEntry.package_version,
            NPMRegistryEntry.source_url,
            NPMRegistryEntry.git_head,
            NPMRegistryEntry.tarball,
        )
        .filter_by(package_name=package_name)
        .order_by(NPMRegistryEntry.published_at.desc())
    )
    # filter for indicated version (if any)
    if package_version is not None:
        query = query.filter_by(package_version=package_version)
    return query


def get_NPMRegistryEntry(package: str, version: str) -> sqlalchemy.orm.query.Query:
    return (
        db.session.query(NPMRegistryEntry)
        .filter_by(package_name=package, package_version=version)
        .order_by(
            NPMRegistryEntry.inserted_at.desc(), NPMRegistryEntry.inserted_at.desc()
        )
    )


def get_maintainers_contributors(
    package: str, version: str
) -> sqlalchemy.orm.query.Query:
    return db.session.query(
        NPMRegistryEntry.maintainers, NPMRegistryEntry.contributors
    ).filter_by(package_name=package, package_version=version)


def get_package_name_in_npm_registry_data(package_name: str) -> Optional[int]:
    return (
        db.session.query(NPMRegistryEntry.id)
        .filter_by(package_name=package_name)
        .limit(1)
        .one_or_none()
    )


def get_package_names_with_missing_npm_entries() -> sqlalchemy.orm.query.Query:
    """
    Returns PackageVersion names not in npmsio_scores.

    >>> from depobs.website.do import create_app
    >>> with create_app(dict(INIT_DB=False)).app_context():
    ...     str(get_package_names_with_missing_npm_entries())
    ...
    'SELECT DISTINCT package_versions.name AS anon_1 \\nFROM package_versions LEFT OUTER JOIN npm_registry_entries ON package_versions.name = npm_registry_entries.package_name \\nWHERE npm_registry_entries.id IS NULL ORDER BY package_versions.name ASC'
    """
    return (
        db.session.query(sqlalchemy.distinct(PackageVersion.name))
        .outerjoin(
            NPMRegistryEntry, PackageVersion.name == NPMRegistryEntry.package_name
        )
        .filter(NPMRegistryEntry.id == None)
        .order_by(PackageVersion.name.asc())
    )


def get_npm_registry_data(package: str, version: str) -> sqlalchemy.orm.query.Query:
    return (
        db.session.query(
            NPMRegistryEntry.published_at,
            NPMRegistryEntry.maintainers,
            NPMRegistryEntry.contributors,
        )
        .filter_by(package_name=package, package_version=version)
        .order_by(NPMRegistryEntry.inserted_at.desc())
    )


def get_vulnerability_counts(package: str, version: str) -> sqlalchemy.orm.query.Query:
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


def get_vulnerabilities(package: str, version: str) -> sqlalchemy.orm.query.Query:
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


def get_statistics() -> Dict[str, int]:
    pkg_version_count = (
        db.session.query(PackageVersion.name, PackageVersion.version,)
        .distinct()
        .count()
    )
    advisories_count = db.session.query(Advisory.id).count()
    reports_count = db.session.query(PackageReport.id).count()
    return dict(
        package_versions=pkg_version_count,
        advisories=advisories_count,
        reports=reports_count,
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


def store_package_report(pr: PackageReport) -> None:
    db.session.add(pr)
    db.session.commit()


def store_package_reports(prs: List[PackageReport]) -> None:
    db.session.add_all(prs)
    db.session.commit()


def insert_npmsio_scores(npmsio_scores: Iterable[NPMSIOScore]) -> None:
    for score in npmsio_scores:
        # only insert new rows
        if (
            db.session.query(NPMSIOScore.id)
            .filter_by(
                package_name=score.package_name,
                package_version=score.package_version,
                analyzed_at=score.analyzed_at,
            )
            .one_or_none()
        ):
            log.debug(
                f"skipping inserting npms.io score for {score.package_name}@{score.package_version}"
                f" analyzed at {score.analyzed_at}"
            )
        else:
            db.session.add(score)
            db.session.commit()
            log.info(
                f"added npms.io score for {score.package_name}@{score.package_version}"
                f" analyzed at {score.analyzed_at}"
            )


def insert_npm_registry_entries(entries: Iterable[NPMRegistryEntry]) -> None:
    for entry in entries:
        if (
            db.session.query(NPMRegistryEntry.id)
            .filter_by(
                package_name=entry.package_name,
                package_version=entry.package_version,
                shasum=entry.shasum,
                tarball=entry.tarball,
            )
            .one_or_none()
        ):
            log.debug(
                f"skipping inserting npm registry entry for {entry.package_name}@{entry.package_version}"
                f" from {entry.tarball} with sha {entry.shasum}"
            )
        else:
            db.session.add(entry)
            db.session.commit()
            log.info(
                f"added npm registry entry for {entry.package_name}@{entry.package_version}"
                f" from {entry.tarball} with sha {entry.shasum}"
            )


VIEWS: Dict[str, str] = {
    "score_view" : """
    CREATE OR REPLACE VIEW score_view AS
    SELECT package, version,  
    npmsio_score * 100 +
    CASE  
    WHEN all_deps <= 5 THEN 20  
    WHEN all_deps <= 20 THEN 10  
    WHEN all_deps >= 500 THEN -20  
    WHEN all_deps >= 100 THEN -10  
    END +
    CASE WHEN "directVulnsCritical_score" > 0 THEN -20 ELSE 0 END +
    CASE WHEN "directVulnsHigh_score" > 0 THEN -10 ELSE 0 END +
    CASE WHEN "directVulnsMedium_score" > 0 THEN -5 ELSE 0 END +
    CASE WHEN "indirectVulnsCritical_score" > 0 THEN -10 ELSE 0 END +
    CASE WHEN "indirectVulnsHigh_score" > 0 THEN -7 ELSE 0 END +
    CASE WHEN "indirectVulnsMedium_score" > 0 THEN -3 ELSE 0 END
    as score
    from reports
    """
        ''
}


def create_views(engine: sqlalchemy.engine.Engine) -> None:
    connection = engine.connect()
    log.info(f"creating views if they don't exist: {list(VIEWS.keys())}")
    for view_command in VIEWS.values():
        _ = connection.execute(view_command)
    connection.close()


def create_tables_and_views(app: flask.app.Flask) -> None:
    # TODO: fix using the stub for flask.ctx.AppContext
    with app.app_context():  # type: ignore
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


def get_advisories_by_package_versions(
    package_versions: List[PackageVersion],
) -> sqlalchemy.orm.query.Query:
    """
    Returns all advisories that directly impact the provided PackageVersion objects.

    >>> from depobs.website.do import create_app
    >>> with create_app(dict(INIT_DB=False)).app_context():
    ...     str(get_advisories_by_package_versions([PackageVersion(id=932)]))
    ...
    'SELECT advisories.id AS advisories_id, advisories.language AS advisories_language, advisories.package_name AS advisories_package_name, advisories.npm_advisory_id AS advisories_npm_advisory_id, advisories.url AS advisories_url, advisories.severity AS advisories_severity, advisories.cwe AS advisories_cwe, advisories.exploitability AS advisories_exploitability, advisories.title AS advisories_title \\nFROM advisories \\nWHERE advisories.vulnerable_package_version_ids @> %(vulnerable_package_version_ids_1)s'
    """
    return db.session.query(Advisory).filter(
        Advisory.vulnerable_package_version_ids.contains(
            [package_version.id for package_version in package_versions]
        )
    )


def add_new_package_version(pkg: Dict) -> None:
    get_package_version_id_query(pkg).one_or_none() or db.session.add(
        PackageVersion(
            name=pkg.get("name", None),
            version=pkg.get("version", None),
            language="node",
            url=pkg.get(
                "resolved", None
            ),  # is null for the root for npm list and yarn list output
        )
    )


def get_package_version_id_query(pkg: Dict) -> sqlalchemy.orm.query.Query:
    return db.session.query(PackageVersion.id).filter_by(
        name=pkg["name"], version=pkg["version"], language="node"
    )


def get_package_version_link_id_query(
    link: Tuple[int, int]
) -> sqlalchemy.orm.query.Query:
    parent_package_id, child_package_id = link
    return db.session.query(PackageLink.id).filter_by(
        parent_package_id=parent_package_id, child_package_id=child_package_id
    )


def get_node_advisory_id_query(advisory: Dict) -> sqlalchemy.orm.query.Query:
    return db.session.query(Advisory.id).filter_by(language="node", url=advisory["url"])


def insert_package_graph(task_data: Dict) -> None:
    link_ids = []
    for task_dep in task_data.get("dependencies", []):
        add_new_package_version(task_dep)
        db.session.commit()
        parent_package_id = get_package_version_id_query(task_dep).first()

        for dep in task_dep.get("dependencies", []):
            # is fully qualified semver for npm (or file: or github: url), semver for yarn
            name, version = dep.rsplit("@", 1)
            child_package_id = get_package_version_id_query(
                dict(name=name, version=version)
            ).first()

            link_id = get_package_version_link_id_query(
                (parent_package_id, child_package_id)
            ).one_or_none()
            if not link_id:
                db.session.add(
                    PackageLink(
                        child_package_id=child_package_id,
                        parent_package_id=parent_package_id,
                    )
                )
                db.session.commit()
                link_id = get_package_version_link_id_query(
                    (parent_package_id, child_package_id)
                ).first()
            link_ids.append(link_id)

    db.session.add(
        PackageGraph(
            root_package_version_id=get_package_version_id_query(
                task_data["root"]
            ).first()
            if task_data["root"]
            else None,
            link_ids=link_ids,
            package_manager="yarn" if "yarn" in task_data["command"] else "npm",
            package_manager_version=None,
        )
    )
    db.session.commit()


def insert_advisories(advisories: Iterable[Advisory]) -> None:
    for advisory in advisories:
        # TODO: update advisory fields if the advisory to insert is newer
        get_node_advisory_id_query(advisory).one_or_none() or db.session.add(advisory)
        db.session.commit()


def update_advisory_vulnerable_package_versions(
    advisory: Advisory, impacted_versions: Set[str]
) -> None:
    # make sure the advisory we want to update is already in the db
    db_advisory = (
        db.session.query(Advisory.id, Advisory.vulnerable_package_version_ids)
        .filter_by(language="node", url=advisory.url)
        .first()
    )
    # look up PackageVersions for known impacted versions
    impacted_version_package_ids = list(
        vid
        for result in db.session.query(PackageVersion.id)
        .filter(
            PackageVersion.name == advisory.package_name,
            PackageVersion.version.in_(impacted_versions),
        )
        .all()
        for vid in result
    )
    if len(impacted_versions) != len(impacted_version_package_ids):
        log.warning(
            f"missing package versions for {advisory.package_name!r}"
            f" in the db or misparsed audit output version:"
            f" {impacted_versions} {impacted_version_package_ids}"
        )

    # handle null Advisory.vulnerable_package_version_ids
    if db_advisory.vulnerable_package_version_ids is None:
        db.session.query(Advisory.id).filter_by(id=db_advisory.id).update(
            dict(vulnerable_package_version_ids=list())
        )

    # TODO: lock the row?
    vpvids = set(
        list(
            db.session.query(Advisory)
            .filter_by(id=db_advisory.id)
            .first()
            .vulnerable_package_version_ids
        )
    )
    vpvids.update(set(impacted_version_package_ids))

    # update the vulnerable_package_version_ids for the advisory
    db.session.query(Advisory.id).filter_by(id=db_advisory.id).update(
        dict(vulnerable_package_version_ids=sorted(vpvids))
    )
    db.session.commit()
