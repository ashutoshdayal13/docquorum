"""V5 visual recovery plus explicit source-unit query scope for native sources."""
from resource_profile_v5 import install as install_v5


def install():
    profile=install_v5()
    return profile|{'profile':'DocQuorum8B-bounded-v6',
        'native_query_scope':'Bind explicit identifier queries to source units containing the referenced ID; unbound fields visit every unit',
        'query_coverage':'Every supplied root field must have at least one scheduled unit',
        'development_scope':'Native V5 error analysis revealed unrelated rows/values being filled in windows lacking the requested identifier'}
