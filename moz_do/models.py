# Placeholder for model code

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, \
     ForeignKey, event, select
from sqlalchemy.orm import scoped_session, sessionmaker, backref, relation, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Table

import os

DATABASE_URI = os.environ.get('DATABASE_URI', 'postgresql+psycopg2://postgres:postgres@localhost/dependency-observatory')

engine = create_engine(DATABASE_URI,
                       convert_unicode=True)
                       
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))

Base = declarative_base()

def init_db():
    Model.metadata.create_all(bind=engine)

Model = declarative_base(name='Model')
Model.query = db_session.query_property()

dependency = Table(
    'package_dependencies', Base.metadata,
    Column('depends_on_id', Integer, ForeignKey('reports.id')),
    Column('used_by_id', Integer, ForeignKey('reports.id'))
)

class PackageReport(Base):
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
    depends = relationship("PackageReport", secondary=dependency,
                           primaryjoin=id==dependency.c.depends_on_id,
                           secondaryjoin=id==dependency.c.used_by_id,
    )

    def to_dict(self):
        return dict(package=self.package,
        version=self.version,
        release_date=self.release_date,
        scoring_date=self.scoring_date,
        top_score=self.top_score,
        authors = self.authors,
        contributors = self.contributors,
        immediate_deps = self.immediate_deps,
        all_deps = self.all_deps,
        dependencies = [rep.id for rep in self.dependencies]
        )

# this relationship is viewonly and selects the dependencies
package_dependencies = select([
                        dependency.c.depends_on_id, 
                        dependency.c.used_by_id
                        ]).alias()
PackageReport.dependencies = relationship('PackageReport',
                       secondary=package_dependencies,
                       primaryjoin=PackageReport.id==package_dependencies.c.used_by_id,
                       secondaryjoin=PackageReport.id==package_dependencies.c.depends_on_id,
                       viewonly=True)     

def get_package_report(package_name):
    for rep in db_session.query(PackageReport).filter(PackageReport.package==package_name):
        return rep