'''
This file contains the implementation of the function for the shot allocation.
The allocation must iplement the following function:
    - allocate_shots(vcs, shots_assignment) -> vc_shots
        vcs: list of qukit.VirtualCircuit circuit where each circuit has a metadata field containing the number of qubits
        shots_allocation: parameters for the allocation
        vcs_shots: list of tuples (fragment, shots), where fragment is a qukit.VirtualCircuit circuit and shots is the number of shots to assign to the fragment
'''
#Policy shots divider
def allocate_shots(vcs, tot_shots):
    vcs_shots = []
    n_frags = len(vcs)
    shots = tot_shots//n_frags
    for fragment in vcs:
        vcs_shots.append((fragment, int(shots)))
    return vcs_shots