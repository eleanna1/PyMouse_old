

# define permutation function for key generation
def create_conds(params):
    from itertools import product
    conds = list(dict(zip(params, x)) for x in product(*params.values()))
    return conds


# define parameters
global conditions

probe1_params = {'probe': [1], 'duration': [[500, 500]], 'odor_idx': [[1, 2]],
                 'dutycycle': [[100, 0], [90, 10], [80, 20], [70, 30], [60, 40], [50, 50]]}
probe2_params = {'probe': [2], 'duration': [[500, 500]], 'odor_idx': [[2, 1]],
                 'dutycycle': [[100, 0], [90, 10], [80, 20], [70, 30], [60, 40], [50, 50]]}

probe1_conds = create_conds(probe1_params)
probe2_conds = create_conds(probe2_params)

conditions = sum([probe1_conds, probe2_conds], [])


