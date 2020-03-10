
import datetime
import os
import sys

# TODO this is a hack to get things working locally. No doubt there is a better way :)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../database')))

import sqlalchemy
from sqlalchemy import func, tuple_
from sqlalchemy.orm import aliased, Load, load_only

from website import website, models
from website.models import db_session, init_db, PackageReport, PackageLatestReport

from database.src.connect import create_engine, create_session
from database.src.schema import (
    Base,
    Advisory,
    PackageVersion,
    PackageLink,
    PackageGraph,
    NPMSIOScore,
    NPMRegistryEntry,
)

'''
New View
--------
CREATE VIEW latest_reports AS
SELECT * From (
SELECT r.*, row_number() OVER (PARTITION BY package, version ORDER BY scoring_date desc) AS rn
       FROM reports r
     ) r2
WHERE r2.rn = 1;

Test data
---------
delete from reports;

insert into reports (package, version, "scoring_date", "top_score", "all_deps",
	"directVulnsCritical_score", "directVulnsHigh_score", "directVulnsMedium_score", "directVulnsLow_score",
	"indirectVulnsCritical_score", "indirectVulnsHigh_score", "indirectVulnsMedium_score", "indirectVulnsLow_score")
values ('@hapi/boom', '9.0.0', timestamp '2020-01-01 01:01:01.001', 9, 10, 0, 1, 0, 4, 0, 0, 0, 2);

insert into reports (package, version, "scoring_date", "top_score", "all_deps", 
	"directVulnsCritical_score", "directVulnsHigh_score", "directVulnsMedium_score", "directVulnsLow_score",
	"indirectVulnsCritical_score", "indirectVulnsHigh_score", "indirectVulnsMedium_score", "indirectVulnsLow_score")
values ('@hapi/boom', '9.0.0', timestamp '2020-02-02 01:01:01.001', 8, 11, 1, 1, 2, 4, 0, 0, 0, 1);

insert into reports (package, version, "scoring_date", "top_score",  "all_deps",
	"directVulnsCritical_score", "directVulnsHigh_score", "directVulnsMedium_score", "directVulnsLow_score",
	"indirectVulnsCritical_score", "indirectVulnsHigh_score", "indirectVulnsMedium_score", "indirectVulnsLow_score")
values ('@hapi/boom', '9.0.1', timestamp '2020-02-02 01:01:01.001', 8, 12, 2, 5, 2, 4, 0, 0, 6, 7);

insert into reports (package, version, "scoring_date", "top_score",  "all_deps",
	"directVulnsCritical_score", "directVulnsHigh_score", "directVulnsMedium_score", "directVulnsLow_score",
	"indirectVulnsCritical_score", "indirectVulnsHigh_score", "indirectVulnsMedium_score", "indirectVulnsLow_score")
values ('@hapi/code', '8.0.1', timestamp '2020-01-01 01:01:01.001', 7, 13, 0, 0, 0, 2, 0, 0, 0, 2);

insert into reports (package, version, "scoring_date", "top_score",  "all_deps",
	"directVulnsCritical_score", "directVulnsHigh_score", "directVulnsMedium_score", "directVulnsLow_score",
	"indirectVulnsCritical_score", "indirectVulnsHigh_score", "indirectVulnsMedium_score", "indirectVulnsLow_score")
values ('@hapi/hoek', '9.0.3', timestamp '2020-01-01 01:01:01.001', 6, 14, 1, 0, 1, 0, 0, 0, 1, 3);

insert into reports (package, version, "scoring_date", "top_score",  "all_deps",
	"directVulnsCritical_score", "directVulnsHigh_score", "directVulnsMedium_score", "directVulnsLow_score",
	"indirectVulnsCritical_score", "indirectVulnsHigh_score", "indirectVulnsMedium_score", "indirectVulnsLow_score")
values ('@hapi/lab', '22.0.3', timestamp '2020-01-01 01:01:01.001', 5, 15, 2, 0, 0, 0, 1, 2, 0, 0);


expected
	1, 1, 2, 4, 0, 0, 0, 1);
	0, 0, 0, 2, 0, 0, 0, 2);
	1, 0, 1, 0, 0, 0, 1, 3);
	2, 0, 0, 0, 1, 2, 0, 0);
Tot 4  1  3  6  1  2  1  6
	crit	4 + 1 = 5
	high	1 + 2 = 3
	med		3 + 1 = 4
	low		6 + 6 = 12

expected all_deps = 4 + 11 + 13 + 14 + 15 = 57

'''

def get_npms_io_score(
    session: sqlalchemy.orm.Session, package: str, version: str
) -> sqlalchemy.orm.query.Query:
    return session.query(NPMSIOScore.score).filter_by(package_name=package, package_version=version)

def get_NPMRegistryEntry(
    session: sqlalchemy.orm.Session, package: str, version: str
) -> sqlalchemy.orm.query.Query:
    return session.query(NPMRegistryEntry).filter_by(package_name=package, package_version=version)

def get_maintainers_contributors(
    session: sqlalchemy.orm.Session, package: str, version: str
) -> sqlalchemy.orm.query.Query:
    return session.query(NPMRegistryEntry.maintainers, NPMRegistryEntry.contributors).filter_by(package_name=package, package_version=version)

def get_npm_registry_data(
    session: sqlalchemy.orm.Session, package: str, version: str
) -> sqlalchemy.orm.query.Query:
    return session.query(NPMRegistryEntry.published_at, NPMRegistryEntry.maintainers, NPMRegistryEntry.contributors).filter_by(package_name=package, package_version=version)

def get_direct_dependencies(
    session: sqlalchemy.orm.Session, package: str, version: str
) -> sqlalchemy.orm.query.Query:
    palias = aliased(PackageVersion)
    calias = aliased(PackageVersion)
    return session.query(calias.name, calias.version
    ).filter(PackageLink.parent_package_id==palias.id
    ).filter(palias.name==package
    ).filter(palias.version==version
    ).filter(PackageLink.child_package_id==calias.id)

def get_vulnerability_counts(
    session: sqlalchemy.orm.Session, package: str, version: str
) -> sqlalchemy.orm.query.Query:
    return session.query(Advisory.package_name, PackageVersion.version, Advisory.severity, 
        func.count(Advisory.severity)
    ).filter_by(package_name=package
    ).filter(PackageVersion.version==version
    ).filter(Advisory.package_name==PackageVersion.name
    ).group_by(Advisory.package_name, PackageVersion.version, Advisory.severity)

def get_direct_dependency_reports(
    session: sqlalchemy.orm.Session, package: str, version: str
) -> sqlalchemy.orm.query.Query:
    palias = aliased(PackageVersion)
    calias = aliased(PackageVersion)
    return session.query(calias.name, calias.version, PackageLatestReport.scoring_date, PackageLatestReport.top_score, PackageLatestReport.all_deps,
        PackageLatestReport.directVulnsCritical_score, PackageLatestReport.directVulnsHigh_score, PackageLatestReport.directVulnsMedium_score, PackageLatestReport.directVulnsLow_score,
        PackageLatestReport.indirectVulnsCritical_score, PackageLatestReport.indirectVulnsHigh_score, PackageLatestReport.indirectVulnsMedium_score, PackageLatestReport.indirectVulnsLow_score
    ).filter(PackageLink.parent_package_id==palias.id
    ).filter(palias.name==package
    ).filter(palias.version==version
    ).filter(PackageLink.child_package_id==calias.id
    ).filter(PackageLatestReport.package==calias.name
    ).filter(PackageLatestReport.version==calias.version)


DATABASE_URI = os.environ.get('DATABASE_URI', 'postgresql+psycopg2://postgres:postgres@localhost/dependency_observatory')

def score_package(pkgname, version):
    engine = create_engine(DATABASE_URI)

    with create_session(engine) as session:
        pr = PackageReport()
        pr.package = pkgname
        pr.version = version

        plr = PackageLatestReport()
        plr.package = pkgname
        plr.version = version

        stmt = get_npms_io_score(session, pkgname, version)
        pr.npmsio_score = stmt.first()

        pr.directVulnsCritical_score = 0
        pr.directVulnsHigh_score = 0
        pr.directVulnsMedium_score = 0
        pr.directVulnsLow_score = 0

        # Direct vulnerability counts
        stmt = get_vulnerability_counts(session, pkgname, version)
        for package, version, severity, count in stmt:
            # This is not yet tested - need real data
            print('\t' + package + '\t' + version + '\t' + severity + '\t' + str(count))
            if severity == 'critical':
                pr.directVulnsCritical_score = count
            elif severity == 'high':
                pr.directVulnsHigh_score = count
            elif severity == 'medium':
                pr.directVulnsMedium_score = count
            elif severity == 'low':
                pr.directVulnsLow_score = count
            else:
                print('TODO log issue - unexpected severity ' + severity)

        stmt = get_npm_registry_data(session, pkgname, version)
        for published_at, maintainers, contributors in stmt:
            pr.release_date = published_at
            if maintainers is not None:
                pr.authors = len(maintainers)
            else:
                pr.authors = 0
            if contributors is not None:
                pr.contributors = len(contributors)
            else:
                pr.contributors = 0

        pr.immediate_deps = get_direct_dependencies(session, pkgname, version).count()

        # Indirect counts
        pr.all_deps = 0
        stmt = get_direct_dependency_reports(session, pkgname, version)
        pr.indirectVulnsCritical_score = 0
        pr.indirectVulnsHigh_score = 0
        pr.indirectVulnsMedium_score = 0
        pr.indirectVulnsLow_score = 0

        dep_rep_count = 0
        for package, version, scoring_date, top_score, all_deps, directVulnsCritical_score, directVulnsHigh_score, directVulnsMedium_score, directVulnsLow_score, indirectVulnsCritical_score, indirectVulnsHigh_score, indirectVulnsMedium_score, indirectVulnsLow_score in stmt:
            dep_rep_count += 1
            pr.all_deps += 1 + all_deps
            pr.indirectVulnsCritical_score += directVulnsCritical_score + indirectVulnsCritical_score
            pr.indirectVulnsHigh_score += directVulnsHigh_score + indirectVulnsHigh_score
            pr.indirectVulnsMedium_score += directVulnsMedium_score + indirectVulnsMedium_score
            pr.indirectVulnsLow_score += directVulnsLow_score + indirectVulnsLow_score

        if dep_rep_count != pr.immediate_deps:
            print('TODO log issue - expected ' + str(pr.immediate_deps) + ' dependencies but got ' + str(dep_rep_count))

        # TODO calculate the top_score, unless this is done in the UI??
        #pr.top_score = 10
        pr.scoring_date = datetime.datetime.now()

        db_session.add(pr)
        db_session.commit()


if __name__ == "__main__":
    score_package('@hapi/bounce', '2.0.0')
