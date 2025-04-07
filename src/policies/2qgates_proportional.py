'''
This file contains the implementation of the function for the shot allocation.
The allocation must iplement the following function:
<<<<<<< HEAD
    - allocate_shots(vcs, shots_assignment) -> vc_shots
=======
    - calculate_shots(vcs, shots_assignment) -> vc_shots
>>>>>>> 3c1d0a0f15e55ffadfb9dd144a121366ef72b917
        vcs: list of qukit.VirtualCircuit circuit where each circuit has a metadata field containing the number of qubits
        shots_allocation: parameters for the allocation
        vcs_shots: list of tuples (fragment, shots), where fragment is a qukit.VirtualCircuit circuit and shots is the number of shots to assign to the fragment
'''
<<<<<<< HEAD
def allocate_shots(vcs, tot_shots):
=======
def calculate_shots(vcs, tot_shots):
>>>>>>> 3c1d0a0f15e55ffadfb9dd144a121366ef72b917
    vcs_shots = []
    tot_2q_gates = sum([c.describe()["num_2q_gates"] for c in vcs])
    for fragment in vcs:
        _2q_gates = fragment.describe()["num_2q_gates"]
        vcs_shots.append((fragment, int(_2q_gates/tot_2q_gates*tot_shots)))
    return vcs_shots