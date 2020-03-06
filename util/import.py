from moz_do.models import db_session, init_db, PackageReport

import json

def load_object(obj):
    print("load object: %s" % (obj))
    pr = PackageReport()
    pr.package = obj['package']
    pr.version = obj['version']
    pr.release_date = obj['release_date']
    pr.scoring_date = obj['scoring_date']
    pr.top_score = obj['top_score']
    pr.authors = obj['authors']
    pr.contributors = obj['contributors']
    pr.immediate_deps = obj['immediate_deps']
    pr.all_deps = obj['all_deps']
    for dep in obj['dependencies']:
        dep_obj = load_object(dep)
        print("dep_obj is %s" % dep_obj.to_dict())
        pr.dependencies.append(dep_obj)
    print("adding: %s" % pr.to_dict())
    db_session.add(pr)
    db_session.commit()
    print("id is %i " % pr.id)
    return pr

if __name__ == "__main__":
    json_data = open('test_data.json','r').read()
    dicts = json.loads(json_data)
    print(dicts)
    pr = load_object(dicts)
    print(pr.to_dict())


