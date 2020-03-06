# Placeholder for model code

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, \
     ForeignKey, event, select
from sqlalchemy.orm import scoped_session, sessionmaker, backref, relation, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Table

import os

DATABASE_URI = os.environ.get('DATABASE_URI', 'postgresql+psycopg2://postgres:postgres@localhost/dependency_observatory')

engine = create_engine(DATABASE_URI,
                       convert_unicode=True)
                       
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))

Model = declarative_base()
# Model.query = db_session.query_property()

dependency = Table(
    'package_dependencies', Model.metadata,
    Column('depends_on_id', Integer, ForeignKey('reports.id'), primary_key=True),
    Column('used_by_id', Integer, ForeignKey('reports.id'), primary_key=True)
)

class PackageReport(Model):
    __tablename__ = 'reports'

    id = Column('id', Integer, primary_key=True)

    package = Column(String(200))
    version = Column(String(200))
    release_date = Column(DateTime)
    scoring_date = Column(DateTime)
    top_score = Column(Integer)
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

    def json_with_dependencies(self):
        return dict(
            id=self.id,
            package=self.package,
            version=self.version,
            release_date=self.release_date,
            scoring_date=self.scoring_date,
            top_score=self.top_score,
            authors = self.authors,
            contributors = self.contributors,
            immediate_deps = self.immediate_deps,
            all_deps = self.all_deps,
            dependencies = [rep.json_with_dependencies() for rep in self.dependencies]
        )
    
    def json_with_parents(self):
        return dict(
            id=self.id,
            package=self.package,
            version=self.version,
            release_date=self.release_date,
            scoring_date=self.scoring_date,
            top_score=self.top_score,
            authors = self.authors,
            contributors = self.contributors,
            immediate_deps = self.immediate_deps,
            all_deps = self.all_deps,
            parents = [rep.json_with_parents() for rep in self.parents]
        )

def get_package_report(package, version = None):
    if None == version:
        #TODO order-by is hard with semver. Think about splitting out versions
        no_version_query = db_session.query(PackageReport).filter(PackageReport.package==package)
        print("Query is %s" % str(no_version_query))
        for rep in no_version_query:
            return rep
    else:
        for rep in db_session.query(PackageReport).filter(PackageReport.package==package, PackageReport.version==version):
            return rep

#def get_parents(id):
#    return db_session.query(PackageReport).filter(PackageReport.dependemcies.has(PackageReport.id == int(id)))

def init_db():
    Model.metadata.create_all(bind=engine)