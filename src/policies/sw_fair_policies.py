'''
This file contains the implementation of the functions for the shotwise policies.
The policies must implement the following functions:
    - split(backends, shots) -> (dispatch, coefficients)
        backends: list of tuples (provider, backend)
        shots: number of shots to split
        dispatch: dictionary of dictionaries of integers, where dispatch[provider][backend] is the number of shots to send to the backend
        coefficients: dictionary of dictionaries of floats, where coefficients[provider][backend] is the weight of the backend in the policy
    - merge(counts) -> (probs, coefficients)
        counts: dictionary of dictionaries of lists, where counts[provider][backend] is a list of tuples (circuit_id, observable, counts)
        probs: dictionary of dictionaries of floats, where probs[(circuit_id,observable)][state] is the probability of measuring the state in the circuit
        coefficients: dictionary of dictionaries of floats, where coefficients[provider][backend] is the weight of the backend in the policy
'''
def split(backends, shots):
    coefficients = fair_policy(backends)
    dispatch = {}
    for provider in coefficients:
        dispatch[provider] = {}
        for backend in coefficients[provider]:
            dispatch[provider][backend] = int(coefficients[provider][backend]*shots)
            
    tot_shots = sum([sum(dispatch[provider].values()) for provider in dispatch])
    diff_shots = tot_shots - shots
    
    if diff_shots > 0:
        for i in range(diff_shots):
            provider,backend = backends[i]
            dispatch[provider][backend] -= 1
    elif diff_shots < 0:
        for i in range(-diff_shots):
            provider,backend = backends[i]
            dispatch[provider][backend] += 1
    dispatch_ls = []
    for provider in dispatch:
        for backend in dispatch[provider]:
            dispatch_ls.append((provider,backend,dispatch[provider][backend]))
    return dispatch_ls, coefficients

def merge(counts):
    backends = []
    for provider in counts:
        for backend in counts[provider]:
            backends.append((provider,backend))
            
    coefficients = fair_policy(backends)
    probs = {}
    for provider in counts:
        for backend in counts[provider]:
            for fragment_id, observable, fragment_counts in counts[provider][backend]:
                if (fragment_id, observable) not in probs:
                    probs[(fragment_id, observable)] = {}
                for state,count in fragment_counts.items():
                    if state not in probs[(fragment_id, observable)]:
                        probs[(fragment_id, observable)][state] = 0
                    probs[(fragment_id, observable)][state] += count*coefficients[provider][backend]
    for fragment_id_obs in probs:
        total = sum([probs[fragment_id_obs][state] for state in probs[fragment_id_obs]])
        for state in probs[fragment_id_obs]:
            probs[fragment_id_obs][state] /= total
    return probs, coefficients
def fair_policy(backends):
    coefficients = {}
    for provider,backend in backends:
        if provider not in coefficients:
            coefficients[provider] = {}
        coefficients[provider][backend] = 1/len(backends)
    return coefficients


