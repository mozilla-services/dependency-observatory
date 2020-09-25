from datetime import datetime
from functools import cached_property
import logging
from typing import (
    AbstractSet,
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    TypedDict,
    Union,
)
from urllib.parse import urlsplit, urlunsplit

import flask
from flask_migrate import Migrate
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
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, column_property, deferred, relationship
from sqlalchemy.sql import case, expression, func
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import DateTime
from sqlalchemy.schema import Table
from sqlalchemy import func

from depobs.database.schemas import PackageReportSchema
from depobs.website.schemas import JobParamsSchema

log = logging.getLogger(__name__)


db: SQLAlchemy = SQLAlchemy()
migrate = Migrate()

# define type aliases to make ints distinguishable in type annotations
PackageLinkID = int
PackageVersionID = int


class ScanFileURL(TypedDict):
    """
    A filename and URL to use in a scan
    """

    filename: str

    url: str


class utcnow(expression.FunctionElement):
    type = DateTime()


@compiles(utcnow, "postgresql")
def pg_utcnow(element: Any, compiler: Any, **kw: Dict) -> str:
    return "TIMEZONE('utc', CURRENT_TIMESTAMP)"


lang_enum = ENUM("node", "rust", "python", name="language_enum")
package_manager_enum = ENUM("npm", "yarn", name="package_manager_enum")
# scans transition from queued -> started -> {succeeded, failed}
scan_status_enum = ENUM(
    "queued", "started", "failed", "succeeded", name="scan_status_enum"
)


class Dependency(db.Model):
    __tablename__ = "package_dependencies"

    depends_on_id = Column(Integer, ForeignKey("reports.id"), primary_key=True)
    used_by_id = Column(Integer, ForeignKey("reports.id"), primary_key=True)


class PackageReport(db.Model):
    __tablename__ = "reports"

    id = Column("id", Integer, primary_key=True)
    package = Column(String(200))
    version = Column(String(200))
    release_date = Column(DateTime)
    scoring_date = Column(DateTime)
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

    @staticmethod
    def score_vulns(
        directVulnsCritical_score: int,
        directVulnsHigh_score: int,
        directVulnsMedium_score: int,
        directVulnsLow_score: int,
        indirectVulnsCritical_score: int,
        indirectVulnsHigh_score: int,
        indirectVulnsMedium_score: int,
        indirectVulnsLow_score: int,
    ) -> int:
        """
        Returns the vulns score contributions per the v1 scoring alg
        """
        return (
            (-30 * directVulnsCritical_score if directVulnsCritical_score > 0 else 0)
            + (-15 * directVulnsHigh_score if directVulnsHigh_score > 0 else 0)
            + (-7 * directVulnsMedium_score if directVulnsMedium_score > 0 else 0)
            + (
                -15 * indirectVulnsCritical_score
                if indirectVulnsCritical_score > 0
                else 0
            )
            + (-7 * indirectVulnsHigh_score if indirectVulnsHigh_score > 0 else 0)
            + (-4 * indirectVulnsMedium_score if indirectVulnsMedium_score > 0 else 0)
        )

    @staticmethod
    def score_all_deps(all_deps: Optional[int]) -> int:
        """
        Returns the all_deps score contribution per the v1 scoring alg
        """
        if not all_deps:
            return 0
        elif all_deps <= 5:
            return 10
        elif all_deps <= 20:
            return 5
        elif all_deps >= 100:
            return -5
        elif all_deps >= 500:
            return -10
        else:
            return 0

    @hybrid_property
    def score(self) -> int:
        return (
            (self.npmsio_score * 100 if self.npmsio_score else 0)
            + PackageReport.score_all_deps(self.all_deps)
            + PackageReport.score_vulns(
                self.directVulnsCritical_score,
                self.directVulnsHigh_score,
                self.directVulnsMedium_score,
                self.directVulnsLow_score,
                self.indirectVulnsCritical_score,
                self.indirectVulnsHigh_score,
                self.indirectVulnsMedium_score,
                self.indirectVulnsLow_score,
            )
        )

    @score.expression  # type: ignore
    def score(cls):
        return (
            case([(cls.npmsio_score != None, cls.npmsio_score * 100)], else_=0)
            + case(
                [
                    (cls.all_deps <= 5, 10),
                    (cls.all_deps <= 20, 5),
                    (cls.all_deps >= 100, -5),
                    (cls.all_deps >= 500, -5),
                ],
                else_=0,
            )
            + case(
                [
                    (
                        cls.directVulnsCritical_score > 0,
                        -30 * cls.directVulnsCritical_score,
                    ),
                ],
                else_=0,
            )
            + case(
                [
                    (cls.directVulnsHigh_score > 0, -15 * cls.directVulnsHigh_score),
                ],
                else_=0,
            )
            + case(
                [
                    (cls.directVulnsMedium_score > 0, -7 * cls.directVulnsMedium_score),
                ],
                else_=0,
            )
            + case(
                [
                    (
                        cls.indirectVulnsCritical_score > 0,
                        -15 * cls.indirectVulnsCritical_score,
                    ),
                ],
                else_=0,
            )
            + case(
                [
                    (cls.indirectVulnsHigh_score > 0, -7 * cls.indirectVulnsHigh_score),
                ],
                else_=0,
            )
            + case(
                [
                    (
                        cls.indirectVulnsMedium_score > 0,
                        -4 * cls.indirectVulnsMedium_score,
                    ),
                ],
                else_=0,
            )
        )

    @hybrid_property
    def score_code(self) -> str:
        if self.score >= 100:
            return "A"
        elif self.score >= 80:
            return "B"
        elif self.score >= 60:
            return "C"
        elif self.score >= 40:
            return "D"
        else:
            return "E"

    @score_code.expression  # type: ignore
    def score_code(cls):
        return case(
            [
                (cls.score >= 100, "A"),
                (cls.score >= 80, "B"),
                (cls.score >= 60, "C"),
                (cls.score >= 40, "D"),
            ],
            else_="E",
        )

    # this relationship is used for persistence
    dependencies: sqlalchemy.orm.RelationshipProperty = relationship(
        "PackageReport",
        secondary=Dependency.__table__,
        primaryjoin=id == Dependency.__table__.c.depends_on_id,
        secondaryjoin=id == Dependency.__table__.c.used_by_id,
        backref="parents",
    )

    @property
    def report_json(self) -> Dict:
        return PackageReportSchema().dump(self)


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
                PackageLink.id.in_(self.link_ids)
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

    @cached_property
    def distinct_package_reports(self) -> List[PackageReport]:
        return get_package_score_reports(
            self.distinct_package_versions_by_id.values()
        ).all()

    @cached_property
    def distinct_package_reports_json(self) -> List[Dict]:
        return [pr.report_json for pr in self.distinct_package_reports]

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
    ) -> Dict[PackageVersionID, Tuple[str, Dict[str, float]]]:
        """
        Returns a dict of package version ID to:

        Tuple[desired_package_version: str, Dict[scored_package_version: str, score: float]]

        ordered by analyzed_at field.

        e.g. {0: ('0.0.0', {'2.0.0': 0.75, '1.0.0': 0.3})}
        """
        # TODO: fetch all scores in one request
        # not cached since it can change as scores are updated
        def get_package_scores_by_version(
            package_version: PackageVersion,
        ) -> Dict[str, float]:
            return {
                score_model.package_version: score_model.score
                for score_model in (
                    get_npmsio_score_query(
                        package_version.name, package_version.version
                    ).all()
                    or get_npmsio_score_query(package_version.name).all()
                )
            }

        return {
            package_version.id: (
                package_version.version,
                get_package_scores_by_version(package_version),
            )
            for package_version in self.distinct_package_versions_by_id.values()
        }

    def get_advisories_by_package_version_id(
        self,
    ) -> Dict[PackageVersionID, List["Advisory"]]:
        # TOOD: fetch all with one DB call
        return {
            package_version.id: get_advisories_by_package_version_ids_query(
                [package_version.id]
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
    shasum = Column(String, nullable=False, primary_key=True)
    # from .versions[<version>].dist.tarball e.g. https://registry.npmjs.org/backoff/-/backoff-2.5.0.tgz
    tarball = Column(String, nullable=False, primary_key=True)

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

    # dependencies: a mapping of other packages this version depends on to the required semver ranges
    # optionalDependencies: an object mapping package names to the required semver ranges of optional dependencies
    # devDependencies: a mapping of package names to the required semver ranges of development dependencies
    # bundleDependencies: an array of dependencies bundled with this version
    # peerDependencies: a mapping of package names to the required semver ranges of peer dependencies

    # saved as: {name: <dependent_pkg_name>, version_range: <version range>, type_prefix: (optional, dev, bundle, peer, "")}
    constraints = deferred(Column(JSONB, nullable=True))

    # scripts e.g. {'docco': 'docco lib/*.js lib/strategy/* index.js',
    #               'pretest': 'jshint lib/ tests/ examples/ index.js',
    #               'test': 'node_modules/nodeunit/bin/nodeunit tests/'}
    scripts = deferred(Column(JSONB, nullable=True))

    # TODO: add the following fields?
    #
    # main: the package's entry point (e.g., index.js or main.js)
    # deprecated: the deprecation warnings message of this version
    # bin: a mapping of bin commands to set up for this version
    # directories: an array of directories included by this version
    # engines: the node engines required for this version to run, if specified e.g. {'node': '>= 0.6'}
    # readme: the first 64K of the README data for the most-recently published version of the package
    # readmeFilename: The name of the file from which the readme data was taken.
    #
    # files e.g. ['index.js', 'lib', 'tests']

    @cached_property
    def normalized_repo_url(self) -> Optional[str]:
        (scheme, netloc, path, query, fragment_identifier) = urlsplit(
            self.repository_url
        )
        if netloc == "github.com":
            return urlunsplit(("https", "github.com", path.replace(".git", ""), "", ""))
        return None

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


class JSONResult(db.Model):
    """
    A table to cache or sample results from HTTP clients and scan jobs
    for debugging without rerunning jobs.
    """

    __tablename__ = "json_results"

    id = Column(Integer, primary_key=True)
    # track when it was inserted
    inserted_at = deferred(Column(DateTime(timezone=False), server_default=utcnow()))

    data = Column("data", JSONB)

    url = Column(String)


class Scan(db.Model):
    """
    Pending, running, and completed package scans
    """

    __tablename__ = "scans"

    id = Column(Integer, primary_key=True)

    # track when it was inserted and changed
    inserted_at = deferred(Column(DateTime(timezone=False), server_default=utcnow()))
    updated_at = deferred(Column(DateTime(timezone=False), onupdate=utcnow()))

    # blob of scan name, version, args, and kwargs
    params = Column("params", JSONB)

    # scan status
    status = Column(scan_status_enum, nullable=False)

    # resulting scan graph id
    graph_id = Column(Integer, nullable=True)

    @cached_property
    def name(
        self,
    ) -> str:
        assert isinstance(self.params, dict)
        return self.params["name"]

    @cached_property
    def package_name(self) -> str:
        return self.get_package_name()

    def get_package_name(
        self,
    ) -> str:
        """
        >>> from depobs.website.do import create_app
        >>> with create_app().app_context():
        ...     Scan(params={"name": "scan_score_npm_package", "args": ["test-pkg-name"]}).get_package_name()
        'test-pkg-name'

        >>> with create_app().app_context():
        ...     Scan(params={"args": ["test-pkg-name"]}).get_package_name()
        Traceback (most recent call last):
        ...
        KeyError: 'name'
        """
        assert isinstance(self.params, dict)
        assert self.name == "scan_score_npm_package"
        return self.params["args"][0]

    @cached_property
    def package_version(
        self,
    ) -> Optional[str]:
        return self.get_package_version()

    def get_package_version(
        self,
    ) -> Optional[str]:
        """
        >>> from depobs.website.do import create_app
        >>> with create_app().app_context():
        ...     Scan(params={"name": "scan_score_npm_package", "args": ["test-pkg-name", "0.0.0"]}).get_package_version()
        '0.0.0'

        >>> with create_app().app_context():
        ...     Scan(params={"name": "scan_score_npm_package", "args": ["test-pkg-name", "latest"]}).get_package_version()
        'latest'

        >>> with create_app().app_context():
        ...     Scan(params={"args": ["test-pkg-name"]}).get_package_version()

        """
        assert isinstance(self.params, dict)
        if len(self.params["args"]) > 1:
            return self.params["args"][1]
        return None

    def dep_file_urls(
        self,
    ) -> Generator[ScanFileURL, None, None]:
        assert isinstance(self.params, dict)
        for file_config in self.params["kwargs"]["dep_file_urls"]:
            yield file_config

    @cached_property
    def report_url(
        self,
    ) -> str:
        """
        Returns the report URL for the scan type and args
        """
        if self.name == "scan_score_npm_package":
            if self.package_version:
                return f"/package_report?package_name={self.package_name}&package_version={self.package_version}&package_manager=npm"
            else:
                return f"/package_report?package_name={self.package_name}&package_manager=npm"
        elif self.name == "scan_score_npm_dep_files":
            return f"/dep_files_reports/{self.id}"

        raise NotImplementedError("report_url not implemented")

    @cached_property
    def package_graph(
        self,
    ) -> Optional[PackageGraph]:
        if self.graph_id:
            return get_graph_by_id(self.graph_id)
        return None


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


def get_package_score_reports(
    package_versions: Iterable[PackageVersion],
) -> sqlalchemy.orm.query.Query:
    """
    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     str(get_package_score_reports([PackageVersion(name="foo", version="0.0.1"), PackageVersion(name="bar", version="0.1.1"),]))
    'SELECT reports.id AS reports_id, reports.package AS reports_package, reports.version AS reports_version, reports.release_date AS reports_release_date, reports.scoring_date AS reports_scoring_date, reports.npmsio_score AS reports_npmsio_score, reports.npmsio_scored_package_version AS reports_npmsio_scored_package_version, reports."directVulnsCritical_score" AS "reports_directVulnsCritical_score", reports."directVulnsHigh_score" AS "reports_directVulnsHigh_score", reports."directVulnsMedium_score" AS "reports_directVulnsMedium_score", reports."directVulnsLow_score" AS "reports_directVulnsLow_score", reports."indirectVulnsCritical_score" AS "reports_indirectVulnsCritical_score", reports."indirectVulnsHigh_score" AS "reports_indirectVulnsHigh_score", reports."indirectVulnsMedium_score" AS "reports_indirectVulnsMedium_score", reports."indirectVulnsLow_score" AS "reports_indirectVulnsLow_score", reports.authors AS reports_authors, reports.contributors AS reports_contributors, reports.immediate_deps AS reports_immediate_deps, reports.all_deps AS reports_all_deps, reports.graph_id AS reports_graph_id \\nFROM reports \\nWHERE (reports.package, reports.version) IN ((%(param_1)s, %(param_2)s), (%(param_3)s, %(param_4)s))'
    """
    return db.session.query(PackageReport).filter(
        sqlalchemy.sql.expression.tuple_(
            PackageReport.package, PackageReport.version
        ).in_([(p.name, p.version) for p in package_versions])
    )


def get_most_recently_scored_package_report_query(
    package_name: str,
    package_version: Optional[str] = None,
    scored_after: Optional[datetime] = None,
) -> sqlalchemy.orm.query.Query:
    """
    Get the most recently scored PackageReport with package_name, optional package_version, and optionally scored_after the scored_after datetime or None

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     str(get_most_recently_scored_package_report_query("foo", "0.0.1"))
    'SELECT reports.id AS reports_id, reports.package AS reports_package, reports.version AS reports_version, reports.release_date AS reports_release_date, reports.scoring_date AS reports_scoring_date, reports.npmsio_score AS reports_npmsio_score, reports.npmsio_scored_package_version AS reports_npmsio_scored_package_version, reports."directVulnsCritical_score" AS "reports_directVulnsCritical_score", reports."directVulnsHigh_score" AS "reports_directVulnsHigh_score", reports."directVulnsMedium_score" AS "reports_directVulnsMedium_score", reports."directVulnsLow_score" AS "reports_directVulnsLow_score", reports."indirectVulnsCritical_score" AS "reports_indirectVulnsCritical_score", reports."indirectVulnsHigh_score" AS "reports_indirectVulnsHigh_score", reports."indirectVulnsMedium_score" AS "reports_indirectVulnsMedium_score", reports."indirectVulnsLow_score" AS "reports_indirectVulnsLow_score", reports.authors AS reports_authors, reports.contributors AS reports_contributors, reports.immediate_deps AS reports_immediate_deps, reports.all_deps AS reports_all_deps, reports.graph_id AS reports_graph_id \\nFROM reports \\nWHERE reports.package = %(package_1)s AND reports.version = %(version_1)s ORDER BY reports.scoring_date DESC \\n LIMIT %(param_1)s'

    """
    query = db.session.query(PackageReport).filter_by(package=package_name)
    if package_version is not None:
        query = query.filter_by(version=package_version)
    if scored_after is not None:
        query = query.filter(PackageReport.scoring_date >= scored_after)
    log.debug(f"Query is {query}")
    return query.order_by(PackageReport.scoring_date.desc()).limit(1)


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


def get_npmsio_score_query(
    package_name: str, package_version: Optional[str] = None
) -> sqlalchemy.orm.query.Query:
    """
    Returns the npms.io score model for the given package name and
    optional version ordered by most recently analyzed.

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     just_name_query = str(get_npmsio_score_query("package_foo"))
    ...     name_and_version_query = str(get_npmsio_score_query("package_foo", "version_1"))

    >>> just_name_query
    'SELECT npmsio_scores.id AS npmsio_scores_id, npmsio_scores.package_name AS npmsio_scores_package_name, npmsio_scores.package_version AS npmsio_scores_package_version, npmsio_scores.analyzed_at AS npmsio_scores_analyzed_at, npmsio_scores.source_url AS npmsio_scores_source_url, npmsio_scores.score AS npmsio_scores_score, npmsio_scores.quality AS npmsio_scores_quality, npmsio_scores.popularity AS npmsio_scores_popularity, npmsio_scores.maintenance AS npmsio_scores_maintenance, npmsio_scores.branding AS npmsio_scores_branding, npmsio_scores.carefulness AS npmsio_scores_carefulness, npmsio_scores.health AS npmsio_scores_health, npmsio_scores.tests AS npmsio_scores_tests, npmsio_scores.community_interest AS npmsio_scores_community_interest, npmsio_scores.dependents_count AS npmsio_scores_dependents_count, npmsio_scores.downloads_count AS npmsio_scores_downloads_count, npmsio_scores.downloads_acceleration AS npmsio_scores_downloads_acceleration, npmsio_scores.commits_frequency AS npmsio_scores_commits_frequency, npmsio_scores.issues_distribution AS npmsio_scores_issues_distribution, npmsio_scores.open_issues AS npmsio_scores_open_issues, npmsio_scores.releases_frequency AS npmsio_scores_releases_frequency \\nFROM npmsio_scores \\nWHERE npmsio_scores.package_name = %(package_name_1)s ORDER BY npmsio_scores.analyzed_at DESC'

    >>> name_and_version_query
    'SELECT npmsio_scores.id AS npmsio_scores_id, npmsio_scores.package_name AS npmsio_scores_package_name, npmsio_scores.package_version AS npmsio_scores_package_version, npmsio_scores.analyzed_at AS npmsio_scores_analyzed_at, npmsio_scores.source_url AS npmsio_scores_source_url, npmsio_scores.score AS npmsio_scores_score, npmsio_scores.quality AS npmsio_scores_quality, npmsio_scores.popularity AS npmsio_scores_popularity, npmsio_scores.maintenance AS npmsio_scores_maintenance, npmsio_scores.branding AS npmsio_scores_branding, npmsio_scores.carefulness AS npmsio_scores_carefulness, npmsio_scores.health AS npmsio_scores_health, npmsio_scores.tests AS npmsio_scores_tests, npmsio_scores.community_interest AS npmsio_scores_community_interest, npmsio_scores.dependents_count AS npmsio_scores_dependents_count, npmsio_scores.downloads_count AS npmsio_scores_downloads_count, npmsio_scores.downloads_acceleration AS npmsio_scores_downloads_acceleration, npmsio_scores.commits_frequency AS npmsio_scores_commits_frequency, npmsio_scores.issues_distribution AS npmsio_scores_issues_distribution, npmsio_scores.open_issues AS npmsio_scores_open_issues, npmsio_scores.releases_frequency AS npmsio_scores_releases_frequency \\nFROM npmsio_scores \\nWHERE npmsio_scores.package_name = %(package_name_1)s AND npmsio_scores.package_version = %(package_version_1)s ORDER BY npmsio_scores.analyzed_at DESC'

    """
    query = (
        db.session.query(NPMSIOScore)
        .filter_by(package_name=package_name)
        .order_by(NPMSIOScore.analyzed_at.desc())
    )
    if package_version:
        query = query.filter_by(package_version=package_version)
    return query


def get_package_names_with_missing_npmsio_scores() -> sqlalchemy.orm.query.Query:
    """
    Returns PackageVersion names not in npmsio_scores.

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     str(get_package_names_with_missing_npmsio_scores())
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
    """
    Returns npm registry entries matching the package name and
    optional package version from most recently published:

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     str(get_npm_registry_entries_to_scan('foo', '1.2.0'))
    ...
    'SELECT npm_registry_entries.package_version AS npm_registry_entries_package_version, npm_registry_entries.source_url AS npm_registry_entries_source_url, npm_registry_entries.git_head AS npm_registry_entries_git_head, npm_registry_entries.tarball AS npm_registry_entries_tarball \\nFROM npm_registry_entries \\nWHERE npm_registry_entries.package_name = %(package_name_1)s AND npm_registry_entries.package_version = %(package_version_1)s ORDER BY npm_registry_entries.published_at DESC'

    >>> with create_app().app_context():
    ...     str(get_npm_registry_entries_to_scan('foo'))
    ...
    'SELECT npm_registry_entries.package_version AS npm_registry_entries_package_version, npm_registry_entries.source_url AS npm_registry_entries_source_url, npm_registry_entries.git_head AS npm_registry_entries_git_head, npm_registry_entries.tarball AS npm_registry_entries_tarball \\nFROM npm_registry_entries \\nWHERE npm_registry_entries.package_name = %(package_name_1)s ORDER BY npm_registry_entries.published_at DESC'

    """
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


def get_NPMRegistryEntry(
    package: str,
    version: Optional[str] = None,
) -> sqlalchemy.orm.query.Query:
    """
    Returns NPMRegistryEntry models for the given package name and
    optional version ordered by most recently inserted.

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     just_name_query = str(get_NPMRegistryEntry("package_foo"))
    ...     name_and_version_query = str(get_NPMRegistryEntry("package_foo", "version_1"))

    >>> just_name_query
    'SELECT npm_registry_entries.id AS npm_registry_entries_id, npm_registry_entries.package_name AS npm_registry_entries_package_name, npm_registry_entries.package_version AS npm_registry_entries_package_version, npm_registry_entries.shasum AS npm_registry_entries_shasum, npm_registry_entries.tarball AS npm_registry_entries_tarball, npm_registry_entries.has_shrinkwrap AS npm_registry_entries_has_shrinkwrap, npm_registry_entries.published_at AS npm_registry_entries_published_at, npm_registry_entries.package_modified_at AS npm_registry_entries_package_modified_at, npm_registry_entries.source_url AS npm_registry_entries_source_url \\nFROM npm_registry_entries \\nWHERE npm_registry_entries.package_name = %(package_name_1)s ORDER BY npm_registry_entries.published_at DESC'

    >>> name_and_version_query
    'SELECT npm_registry_entries.id AS npm_registry_entries_id, npm_registry_entries.package_name AS npm_registry_entries_package_name, npm_registry_entries.package_version AS npm_registry_entries_package_version, npm_registry_entries.shasum AS npm_registry_entries_shasum, npm_registry_entries.tarball AS npm_registry_entries_tarball, npm_registry_entries.has_shrinkwrap AS npm_registry_entries_has_shrinkwrap, npm_registry_entries.published_at AS npm_registry_entries_published_at, npm_registry_entries.package_modified_at AS npm_registry_entries_package_modified_at, npm_registry_entries.source_url AS npm_registry_entries_source_url \\nFROM npm_registry_entries \\nWHERE npm_registry_entries.package_name = %(package_name_1)s AND npm_registry_entries.package_version = %(package_version_1)s ORDER BY npm_registry_entries.published_at DESC'

    """
    query = db.session.query(NPMRegistryEntry).order_by(
        NPMRegistryEntry.published_at.desc()
    )
    if version:
        query = query.filter_by(package_name=package, package_version=version)
    else:
        query = query.filter_by(package_name=package)

    return query


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
    >>> with create_app().app_context():
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


def get_score_code_counts() -> sqlalchemy.orm.query.Query:
    """
    Returns a query returning score codes to their counts from the
    scored reports view.

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     str(get_score_code_counts())
    'SELECT CASE WHEN (CASE WHEN (reports.npmsio_score IS NOT NULL) THEN reports.npmsio_score * %(npmsio_score_1)s ELSE %(param_1)s END + CASE WHEN (reports.all_deps <= %(all_deps_1)s) THEN %(param_2)s WHEN (reports.all_deps <= %(all_deps_2)s) THEN %(param_3)s WHEN (reports.all_deps >= %(all_deps_3)s) THEN %(param_4)s WHEN (reports.all_deps >= %(all_deps_4)s) THEN %(param_5)s ELSE %(param_6)s END + CASE WHEN (reports."directVulnsCritical_score" > %(directVulnsCritical_score_1)s) THEN %(directVulnsCritical_score_2)s * reports."directVulnsCritical_score" ELSE %(param_7)s END + CASE WHEN (reports."directVulnsHigh_score" > %(directVulnsHigh_score_1)s) THEN %(directVulnsHigh_score_2)s * reports."directVulnsHigh_score" ELSE %(param_8)s END + CASE WHEN (reports."directVulnsMedium_score" > %(directVulnsMedium_score_1)s) THEN %(directVulnsMedium_score_2)s * reports."directVulnsMedium_score" ELSE %(param_9)s END + CASE WHEN (reports."indirectVulnsCritical_score" > %(indirectVulnsCritical_score_1)s) THEN %(indirectVulnsCritical_score_2)s * reports."indirectVulnsCritical_score" ELSE %(param_10)s END + CASE WHEN (reports."indirectVulnsHigh_score" > %(indirectVulnsHigh_score_1)s) THEN %(indirectVulnsHigh_score_2)s * reports."indirectVulnsHigh_score" ELSE %(param_11)s END + CASE WHEN (reports."indirectVulnsMedium_score" > %(indirectVulnsMedium_score_1)s) THEN %(indirectVulnsMedium_score_2)s * reports."indirectVulnsMedium_score" ELSE %(param_12)s END >= %(param_13)s) THEN %(param_14)s WHEN (CASE WHEN (reports.npmsio_score IS NOT NULL) THEN reports.npmsio_score * %(npmsio_score_2)s ELSE %(param_15)s END + CASE WHEN (reports.all_deps <= %(all_deps_5)s) THEN %(param_16)s WHEN (reports.all_deps <= %(all_deps_6)s) THEN %(param_17)s WHEN (reports.all_deps >= %(all_deps_7)s) THEN %(param_18)s WHEN (reports.all_deps >= %(all_deps_8)s) THEN %(param_19)s ELSE %(param_20)s END + CASE WHEN (reports."directVulnsCritical_score" > %(directVulnsCritical_score_3)s) THEN %(directVulnsCritical_score_4)s * reports."directVulnsCritical_score" ELSE %(param_21)s END + CASE WHEN (reports."directVulnsHigh_score" > %(directVulnsHigh_score_3)s) THEN %(directVulnsHigh_score_4)s * reports."directVulnsHigh_score" ELSE %(param_22)s END + CASE WHEN (reports."directVulnsMedium_score" > %(directVulnsMedium_score_3)s) THEN %(directVulnsMedium_score_4)s * reports."directVulnsMedium_score" ELSE %(param_23)s END + CASE WHEN (reports."indirectVulnsCritical_score" > %(indirectVulnsCritical_score_3)s) THEN %(indirectVulnsCritical_score_4)s * reports."indirectVulnsCritical_score" ELSE %(param_24)s END + CASE WHEN (reports."indirectVulnsHigh_score" > %(indirectVulnsHigh_score_3)s) THEN %(indirectVulnsHigh_score_4)s * reports."indirectVulnsHigh_score" ELSE %(param_25)s END + CASE WHEN (reports."indirectVulnsMedium_score" > %(indirectVulnsMedium_score_3)s) THEN %(indirectVulnsMedium_score_4)s * reports."indirectVulnsMedium_score" ELSE %(param_26)s END >= %(param_27)s) THEN %(param_28)s WHEN (CASE WHEN (reports.npmsio_score IS NOT NULL) THEN reports.npmsio_score * %(npmsio_score_3)s ELSE %(param_29)s END + CASE WHEN (reports.all_deps <= %(all_deps_9)s) THEN %(param_30)s WHEN (reports.all_deps <= %(all_deps_10)s) THEN %(param_31)s WHEN (reports.all_deps >= %(all_deps_11)s) THEN %(param_32)s WHEN (reports.all_deps >= %(all_deps_12)s) THEN %(param_33)s ELSE %(param_34)s END + CASE WHEN (reports."directVulnsCritical_score" > %(directVulnsCritical_score_5)s) THEN %(directVulnsCritical_score_6)s * reports."directVulnsCritical_score" ELSE %(param_35)s END + CASE WHEN (reports."directVulnsHigh_score" > %(directVulnsHigh_score_5)s) THEN %(directVulnsHigh_score_6)s * reports."directVulnsHigh_score" ELSE %(param_36)s END + CASE WHEN (reports."directVulnsMedium_score" > %(directVulnsMedium_score_5)s) THEN %(directVulnsMedium_score_6)s * reports."directVulnsMedium_score" ELSE %(param_37)s END + CASE WHEN (reports."indirectVulnsCritical_score" > %(indirectVulnsCritical_score_5)s) THEN %(indirectVulnsCritical_score_6)s * reports."indirectVulnsCritical_score" ELSE %(param_38)s END + CASE WHEN (reports."indirectVulnsHigh_score" > %(indirectVulnsHigh_score_5)s) THEN %(indirectVulnsHigh_score_6)s * reports."indirectVulnsHigh_score" ELSE %(param_39)s END + CASE WHEN (reports."indirectVulnsMedium_score" > %(indirectVulnsMedium_score_5)s) THEN %(indirectVulnsMedium_score_6)s * reports."indirectVulnsMedium_score" ELSE %(param_40)s END >= %(param_41)s) THEN %(param_42)s WHEN (CASE WHEN (reports.npmsio_score IS NOT NULL) THEN reports.npmsio_score * %(npmsio_score_4)s ELSE %(param_43)s END + CASE WHEN (reports.all_deps <= %(all_deps_13)s) THEN %(param_44)s WHEN (reports.all_deps <= %(all_deps_14)s) THEN %(param_45)s WHEN (reports.all_deps >= %(all_deps_15)s) THEN %(param_46)s WHEN (reports.all_deps >= %(all_deps_16)s) THEN %(param_47)s ELSE %(param_48)s END + CASE WHEN (reports."directVulnsCritical_score" > %(directVulnsCritical_score_7)s) THEN %(directVulnsCritical_score_8)s * reports."directVulnsCritical_score" ELSE %(param_49)s END + CASE WHEN (reports."directVulnsHigh_score" > %(directVulnsHigh_score_7)s) THEN %(directVulnsHigh_score_8)s * reports."directVulnsHigh_score" ELSE %(param_50)s END + CASE WHEN (reports."directVulnsMedium_score" > %(directVulnsMedium_score_7)s) THEN %(directVulnsMedium_score_8)s * reports."directVulnsMedium_score" ELSE %(param_51)s END + CASE WHEN (reports."indirectVulnsCritical_score" > %(indirectVulnsCritical_score_7)s) THEN %(indirectVulnsCritical_score_8)s * reports."indirectVulnsCritical_score" ELSE %(param_52)s END + CASE WHEN (reports."indirectVulnsHigh_score" > %(indirectVulnsHigh_score_7)s) THEN %(indirectVulnsHigh_score_8)s * reports."indirectVulnsHigh_score" ELSE %(param_53)s END + CASE WHEN (reports."indirectVulnsMedium_score" > %(indirectVulnsMedium_score_7)s) THEN %(indirectVulnsMedium_score_8)s * reports."indirectVulnsMedium_score" ELSE %(param_54)s END >= %(param_55)s) THEN %(param_56)s ELSE %(param_57)s END AS score_code, count(%(count_2)s) AS count_1 \\nFROM reports GROUP BY CASE WHEN (CASE WHEN (reports.npmsio_score IS NOT NULL) THEN reports.npmsio_score * %(npmsio_score_5)s ELSE %(param_58)s END + CASE WHEN (reports.all_deps <= %(all_deps_17)s) THEN %(param_59)s WHEN (reports.all_deps <= %(all_deps_18)s) THEN %(param_60)s WHEN (reports.all_deps >= %(all_deps_19)s) THEN %(param_61)s WHEN (reports.all_deps >= %(all_deps_20)s) THEN %(param_62)s ELSE %(param_63)s END + CASE WHEN (reports."directVulnsCritical_score" > %(directVulnsCritical_score_9)s) THEN %(directVulnsCritical_score_10)s * reports."directVulnsCritical_score" ELSE %(param_64)s END + CASE WHEN (reports."directVulnsHigh_score" > %(directVulnsHigh_score_9)s) THEN %(directVulnsHigh_score_10)s * reports."directVulnsHigh_score" ELSE %(param_65)s END + CASE WHEN (reports."directVulnsMedium_score" > %(directVulnsMedium_score_9)s) THEN %(directVulnsMedium_score_10)s * reports."directVulnsMedium_score" ELSE %(param_66)s END + CASE WHEN (reports."indirectVulnsCritical_score" > %(indirectVulnsCritical_score_9)s) THEN %(indirectVulnsCritical_score_10)s * reports."indirectVulnsCritical_score" ELSE %(param_67)s END + CASE WHEN (reports."indirectVulnsHigh_score" > %(indirectVulnsHigh_score_9)s) THEN %(indirectVulnsHigh_score_10)s * reports."indirectVulnsHigh_score" ELSE %(param_68)s END + CASE WHEN (reports."indirectVulnsMedium_score" > %(indirectVulnsMedium_score_9)s) THEN %(indirectVulnsMedium_score_10)s * reports."indirectVulnsMedium_score" ELSE %(param_69)s END >= %(param_70)s) THEN %(param_71)s WHEN (CASE WHEN (reports.npmsio_score IS NOT NULL) THEN reports.npmsio_score * %(npmsio_score_6)s ELSE %(param_72)s END + CASE WHEN (reports.all_deps <= %(all_deps_21)s) THEN %(param_73)s WHEN (reports.all_deps <= %(all_deps_22)s) THEN %(param_74)s WHEN (reports.all_deps >= %(all_deps_23)s) THEN %(param_75)s WHEN (reports.all_deps >= %(all_deps_24)s) THEN %(param_76)s ELSE %(param_77)s END + CASE WHEN (reports."directVulnsCritical_score" > %(directVulnsCritical_score_11)s) THEN %(directVulnsCritical_score_12)s * reports."directVulnsCritical_score" ELSE %(param_78)s END + CASE WHEN (reports."directVulnsHigh_score" > %(directVulnsHigh_score_11)s) THEN %(directVulnsHigh_score_12)s * reports."directVulnsHigh_score" ELSE %(param_79)s END + CASE WHEN (reports."directVulnsMedium_score" > %(directVulnsMedium_score_11)s) THEN %(directVulnsMedium_score_12)s * reports."directVulnsMedium_score" ELSE %(param_80)s END + CASE WHEN (reports."indirectVulnsCritical_score" > %(indirectVulnsCritical_score_11)s) THEN %(indirectVulnsCritical_score_12)s * reports."indirectVulnsCritical_score" ELSE %(param_81)s END + CASE WHEN (reports."indirectVulnsHigh_score" > %(indirectVulnsHigh_score_11)s) THEN %(indirectVulnsHigh_score_12)s * reports."indirectVulnsHigh_score" ELSE %(param_82)s END + CASE WHEN (reports."indirectVulnsMedium_score" > %(indirectVulnsMedium_score_11)s) THEN %(indirectVulnsMedium_score_12)s * reports."indirectVulnsMedium_score" ELSE %(param_83)s END >= %(param_84)s) THEN %(param_85)s WHEN (CASE WHEN (reports.npmsio_score IS NOT NULL) THEN reports.npmsio_score * %(npmsio_score_7)s ELSE %(param_86)s END + CASE WHEN (reports.all_deps <= %(all_deps_25)s) THEN %(param_87)s WHEN (reports.all_deps <= %(all_deps_26)s) THEN %(param_88)s WHEN (reports.all_deps >= %(all_deps_27)s) THEN %(param_89)s WHEN (reports.all_deps >= %(all_deps_28)s) THEN %(param_90)s ELSE %(param_91)s END + CASE WHEN (reports."directVulnsCritical_score" > %(directVulnsCritical_score_13)s) THEN %(directVulnsCritical_score_14)s * reports."directVulnsCritical_score" ELSE %(param_92)s END + CASE WHEN (reports."directVulnsHigh_score" > %(directVulnsHigh_score_13)s) THEN %(directVulnsHigh_score_14)s * reports."directVulnsHigh_score" ELSE %(param_93)s END + CASE WHEN (reports."directVulnsMedium_score" > %(directVulnsMedium_score_13)s) THEN %(directVulnsMedium_score_14)s * reports."directVulnsMedium_score" ELSE %(param_94)s END + CASE WHEN (reports."indirectVulnsCritical_score" > %(indirectVulnsCritical_score_13)s) THEN %(indirectVulnsCritical_score_14)s * reports."indirectVulnsCritical_score" ELSE %(param_95)s END + CASE WHEN (reports."indirectVulnsHigh_score" > %(indirectVulnsHigh_score_13)s) THEN %(indirectVulnsHigh_score_14)s * reports."indirectVulnsHigh_score" ELSE %(param_96)s END + CASE WHEN (reports."indirectVulnsMedium_score" > %(indirectVulnsMedium_score_13)s) THEN %(indirectVulnsMedium_score_14)s * reports."indirectVulnsMedium_score" ELSE %(param_97)s END >= %(param_98)s) THEN %(param_99)s WHEN (CASE WHEN (reports.npmsio_score IS NOT NULL) THEN reports.npmsio_score * %(npmsio_score_8)s ELSE %(param_100)s END + CASE WHEN (reports.all_deps <= %(all_deps_29)s) THEN %(param_101)s WHEN (reports.all_deps <= %(all_deps_30)s) THEN %(param_102)s WHEN (reports.all_deps >= %(all_deps_31)s) THEN %(param_103)s WHEN (reports.all_deps >= %(all_deps_32)s) THEN %(param_104)s ELSE %(param_105)s END + CASE WHEN (reports."directVulnsCritical_score" > %(directVulnsCritical_score_15)s) THEN %(directVulnsCritical_score_16)s * reports."directVulnsCritical_score" ELSE %(param_106)s END + CASE WHEN (reports."directVulnsHigh_score" > %(directVulnsHigh_score_15)s) THEN %(directVulnsHigh_score_16)s * reports."directVulnsHigh_score" ELSE %(param_107)s END + CASE WHEN (reports."directVulnsMedium_score" > %(directVulnsMedium_score_15)s) THEN %(directVulnsMedium_score_16)s * reports."directVulnsMedium_score" ELSE %(param_108)s END + CASE WHEN (reports."indirectVulnsCritical_score" > %(indirectVulnsCritical_score_15)s) THEN %(indirectVulnsCritical_score_16)s * reports."indirectVulnsCritical_score" ELSE %(param_109)s END + CASE WHEN (reports."indirectVulnsHigh_score" > %(indirectVulnsHigh_score_15)s) THEN %(indirectVulnsHigh_score_16)s * reports."indirectVulnsHigh_score" ELSE %(param_110)s END + CASE WHEN (reports."indirectVulnsMedium_score" > %(indirectVulnsMedium_score_15)s) THEN %(indirectVulnsMedium_score_16)s * reports."indirectVulnsMedium_score" ELSE %(param_111)s END >= %(param_112)s) THEN %(param_113)s ELSE %(param_114)s END'

    """
    # NB: try pulling from pg_stats if we materialize the view later
    return db.session.query(PackageReport.score_code, func.count("1")).group_by(
        PackageReport.score_code
    )


def get_statistics() -> Dict[str, Union[int, Dict[str, int]]]:
    pkg_version_count = (
        db.session.query(
            PackageVersion.name,
            PackageVersion.version,
        )
        .distinct()
        .count()
    )
    advisories_count = db.session.query(Advisory.id).count()
    reports_count = db.session.query(PackageReport.id).count()
    return dict(
        package_versions=pkg_version_count,
        advisories=advisories_count,
        reports=reports_count,
        score_codes_histogram={
            score_code: score_code_count
            for (score_code, score_code_count) in get_score_code_counts().all()
        },
    )


def get_statistics_scores() -> List[int]:
    scores = db.session.query(PackageReport.score).all()
    scores = [int(score[0]) for score in scores if len(score) and score[0]]
    return scores


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


def get_advisories_by_package_version_ids_query(
    package_version_ids: List[PackageVersionID],
) -> sqlalchemy.orm.query.Query:
    """
    Returns all advisories that directly impact the provided PackageVersion ids.

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     str(get_advisories_by_package_version_ids_query([932]))
    ...
    'SELECT advisories.id AS advisories_id, advisories.language AS advisories_language, advisories.package_name AS advisories_package_name, advisories.npm_advisory_id AS advisories_npm_advisory_id, advisories.url AS advisories_url, advisories.severity AS advisories_severity, advisories.cwe AS advisories_cwe, advisories.exploitability AS advisories_exploitability, advisories.title AS advisories_title \\nFROM advisories \\nWHERE advisories.vulnerable_package_version_ids && %(vulnerable_package_version_ids_1)s'
    """
    return db.session.query(Advisory).filter(
        Advisory.vulnerable_package_version_ids.overlap(
            [package_version_id for package_version_id in package_version_ids]
        )
    )


def get_package_version_id_query(
    package_version: PackageVersion,
) -> sqlalchemy.orm.query.Query:
    """
    Returns query to select a node package version id by name and version

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     str(get_package_version_id_query(PackageVersion(name='foo', version='0.0.0-test')))
    'SELECT package_versions.id AS package_versions_id \\nFROM package_versions \\nWHERE package_versions.name = %(name_1)s AND package_versions.version = %(version_1)s AND package_versions.language = %(language_1)s'
    """
    return db.session.query(PackageVersion.id).filter_by(
        name=package_version.name, version=package_version.version, language="node"
    )


def upsert_package_version(package_version: PackageVersion) -> None:
    get_package_version_id_query(package_version).one_or_none() or db.session.add(
        package_version
    )


def get_package_version_link_id_query(link: PackageLink) -> sqlalchemy.orm.query.Query:
    """
    Returns query to select a package version link by child and parent PackageVersion ids

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     str(get_package_version_link_id_query(PackageLink(parent_package_id=38, child_package_id=5)))
    'SELECT package_links.id AS package_links_id \\nFROM package_links \\nWHERE package_links.parent_package_id = %(parent_package_id_1)s AND package_links.child_package_id = %(child_package_id_1)s'
    """
    return db.session.query(PackageLink.id).filter_by(
        parent_package_id=link.parent_package_id, child_package_id=link.child_package_id
    )


def upsert_package_links(links: Iterable[PackageLink]) -> None:
    """
    Upserts package links
    """
    for link in links:
        link_id = get_package_version_link_id_query(link).one_or_none()
        if not link_id:
            db.session.add(link)


def get_node_advisory_id_query(advisory: Advisory) -> sqlalchemy.orm.query.Query:
    """
    Returns query to select an advisory id by URL

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     str(get_node_advisory_id_query(Advisory(url='https://example.com')))
    'SELECT advisories.id AS advisories_id \\nFROM advisories \\nWHERE advisories.language = %(language_1)s AND advisories.url = %(url_1)s'
    """
    return db.session.query(Advisory.id).filter_by(language="node", url=advisory.url)


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


def save_json_results(json_results: List[Dict]) -> None:
    db.session.add_all(JSONResult(data=json_result) for json_result in json_results)
    db.session.commit()


def get_next_scans() -> sqlalchemy.orm.query.Query:
    """
    Returns the next inserted scans:

    >>> 'queued' in scan_status_enum.enums
    True
    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    'SELECT scans.id AS scans_id, scans.params AS scans_params, scans.status AS scans_status, scans.graph_id AS scans_graph_id \\nFROM scans \\nWHERE scans.status = %(status_1)s ORDER BY scans.inserted_at DESC \\n LIMIT %(param_1)s'
    ...     str(get_next_scans().filter_by(status="queued"))
    """
    return db.session.query(Scan).order_by(Scan.inserted_at.desc())


def get_scan_job_results(job_name: str) -> sqlalchemy.orm.query.Query:
    """
    Returns query for JSONResults from pubsub with the given job_name:

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     str(get_scan_job_results('scan-foo'))
    'SELECT json_results.id AS json_results_id, json_results.data AS json_results_data, json_results.url AS json_results_url \\nFROM json_results \\nWHERE CAST(((json_results.data -> %(data_1)s) ->> %(param_1)s) AS VARCHAR) = %(param_2)s ORDER BY json_results.id DESC'
    """
    return (
        db.session.query(JSONResult)
        .filter(JSONResult.data["attributes"]["JOB_NAME"].as_string() == job_name)
        .order_by(JSONResult.id.desc())
    )


def get_scan_results_by_id(scan_id: int) -> sqlalchemy.orm.query.Query:
    """
    Returns query for JSONResults from pubsub with the given scan_id:

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     str(get_scan_results_by_id(392))
    'SELECT json_results.id AS json_results_id, json_results.data AS json_results_data, json_results.url AS json_results_url \\nFROM json_results \\nWHERE CAST(((json_results.data -> %(data_1)s) ->> %(param_1)s) AS VARCHAR) = %(param_2)s ORDER BY json_results.id ASC'
    """
    return (
        db.session.query(JSONResult)
        .filter(JSONResult.data["attributes"]["SCAN_ID"].as_string() == str(scan_id))
        .order_by(JSONResult.id.asc())
    )


def get_scan_results_by_id_on_job_name(scan_id: int) -> sqlalchemy.orm.query.Query:
    """
    Returns query for JSONResults from pubsub with the given scan_id grouped by job name:

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     str(get_scan_results_by_id_on_job_name(392))
    'SELECT json_results.id AS json_results_id, json_results.data AS json_results_data, json_results.url AS json_results_url \\nFROM json_results \\nWHERE CAST(((json_results.data -> %(data_1)s) ->> %(param_1)s) AS VARCHAR) = %(param_2)s GROUP BY json_results.id, CAST((json_results.data -> %(data_2)s) ->> %(param_3)s AS VARCHAR) ORDER BY json_results.id ASC'
    """
    return get_scan_results_by_id(scan_id).group_by(
        JSONResult.id, JSONResult.data["attributes"]["SCAN_ID"].as_string()
    )


def package_name_and_version_to_scan(
    package_name: str, package_version: Optional[str]
) -> Scan:
    """
    Return a scan model for the given package name and optional
    package_version.
    """
    return Scan(
        params=JobParamsSchema().dump(
            {
                "name": "scan_score_npm_package",
                "args": [package_name, package_version],
            }
        ),
        status="queued",
    )


def dependency_files_to_scan(
    dep_file_urls: List[ScanFileURL],
) -> Scan:
    """
    Return a scan model for the npm dependency files.
    """
    return Scan(
        params=JobParamsSchema().dump(
            {
                "name": "scan_score_npm_dep_files",
                "kwargs": {"dep_file_urls": dep_file_urls},
            }
        ),
        status="queued",
    )


def save_scan_with_status(scan: Scan, status: str) -> Scan:
    scan.status = status
    db.session.add(scan)
    db.session.commit()
    return scan


def save_scan_with_graph_id(scan: Scan, graph_id: int) -> Scan:
    scan.graph_id = graph_id
    db.session.add(scan)
    db.session.commit()
    return scan


def save_deserialized(
    deserialized: Union[
        PackageVersion,
        Tuple[
            PackageGraph,
            Optional[PackageVersion],
            List[Tuple[PackageVersion, PackageVersion]],
        ],
        Tuple[Advisory, AbstractSet[str]],
    ]
) -> None:
    if isinstance(deserialized, PackageVersion):
        upsert_package_version(deserialized)
    elif isinstance(deserialized, tuple) and isinstance(deserialized[0], PackageGraph):
        graph: PackageGraph = deserialized[0]
        root_package_version: Optional[PackageVersion] = deserialized[1]  # type: ignore
        links: List[Tuple[PackageVersion, PackageVersion]] = deserialized[
            2
        ]  # type: ignore
        if root_package_version:
            upsert_package_version(root_package_version)
            db.session.commit()
            root_package_version_with_id = get_package_version_id_query(
                root_package_version
            ).one_or_none()
            graph.root_package_version_id = (
                root_package_version_with_id.id
                if root_package_version_with_id
                else None
            )

        # TODO: combine into one query
        link_ids = []
        for parent, child in links:
            log.debug(
                f"resolving link package version ids for {child.name}@{child.version}->{parent.name}@{parent.version}"
            )
            link = PackageLink(
                parent_package_id=get_package_version_id_query(parent).first().id,
                child_package_id=get_package_version_id_query(child).first().id,
            )
            log.debug(
                f"resolved package version ids for link {link.child_package_id}->{link.parent_package_id}"
            )
            upsert_package_links([link])
            db.session.commit()
            log.debug(f"upserted link {link} w/ id {link.id}")
            link_ids.append(get_package_version_link_id_query(link).first().id)
            log.debug(f"added link id to graph {link_ids[-1]}")

        graph.link_ids = link_ids
        db.session.add(graph)
    elif isinstance(deserialized, tuple) and isinstance(deserialized[0], Advisory):
        advisory, impacted_versions = deserialized  # type: ignore
        insert_advisories([advisory])
        update_advisory_vulnerable_package_versions(advisory, set(impacted_versions))
    else:
        log.warn(f"don't know how to save deserialized {deserialized}")
    db.session.commit()


def get_scan_by_id(scan_id: int) -> Scan:
    """
    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     query = str(get_scan_by_id(20))

    >>> query
    'SELECT scans.id AS scans_id, scans.params AS scans_params, scans.status AS scans_status, scans.graph_id AS scans_graph_id \\nFROM scans \\nWHERE scans.id = %(id_1)s'
    """
    return db.session.query(Scan).filter_by(id=scan_id)


def get_recent_package_reports_query(
    limit: Optional[int] = 10,
) -> sqlalchemy.orm.query.Query:
    """

    >>> from depobs.website.do import create_app
    >>> with create_app().app_context():
    ...     str(get_recent_package_reports_query())
    'SELECT reports.id AS reports_id, reports.package AS reports_package, reports.version AS reports_version, reports.release_date AS reports_release_date, reports.scoring_date AS reports_scoring_date, reports.npmsio_score AS reports_npmsio_score, reports.npmsio_scored_package_version AS reports_npmsio_scored_package_version, reports."directVulnsCritical_score" AS "reports_directVulnsCritical_score", reports."directVulnsHigh_score" AS "reports_directVulnsHigh_score", reports."directVulnsMedium_score" AS "reports_directVulnsMedium_score", reports."directVulnsLow_score" AS "reports_directVulnsLow_score", reports."indirectVulnsCritical_score" AS "reports_indirectVulnsCritical_score", reports."indirectVulnsHigh_score" AS "reports_indirectVulnsHigh_score", reports."indirectVulnsMedium_score" AS "reports_indirectVulnsMedium_score", reports."indirectVulnsLow_score" AS "reports_indirectVulnsLow_score", reports.authors AS reports_authors, reports.contributors AS reports_contributors, reports.immediate_deps AS reports_immediate_deps, reports.all_deps AS reports_all_deps, reports.graph_id AS reports_graph_id \\nFROM reports ORDER BY reports.scoring_date DESC \\n LIMIT %(param_1)s'

    """
    return (
        db.session.query(PackageReport)
        .order_by(PackageReport.scoring_date.desc())
        .limit(limit)
    )
