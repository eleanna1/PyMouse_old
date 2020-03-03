

# define permutation function for key generation
def create_conds(params):
    from itertools import product
    conds = list(dict(zip(params, x)) for x in product(*params.values()))
    return conds


# define parameters
global conditions

probe1_params = {'probe': [1], 'movie_name': ['o3bgv6'], 'clip_number': list(range(1, 10))}
probe2_params = {'probe': [2], 'movie_name': ['o1bgv6'], 'clip_number': list(range(1, 10))}

probe1_conds = create_conds(probe1_params)
probe2_conds = create_conds(probe2_params)

conditions = sum([probe1_conds, probe2_conds], [])


