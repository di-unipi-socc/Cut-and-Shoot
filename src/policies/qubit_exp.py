'''
This file contains the implementation of the function for the shot allocation.
The allocation must iplement the following function:
    - allocate_shots(vcs, shots_assignment) -> vc_shots
        vcs: list of qukit.VirtualCircuit circuit where each circuit has a metadata field containing the number of qubits
        shots_allocation: parameters for the allocation
        vcs_shots: list of tuples (fragment, shots), where fragment is a qukit.VirtualCircuit circuit and shots is the number of shots to assign to the fragment
'''
import numpy as np

def allocate_shots(vcs, tot_shots):
    vcs_shots = []
    qubit_counts = np.array([c.describe()["qubits"] for c in vcs])
    
    # Exponential scaling
    exp_qubits = np.exp(qubit_counts)
    exp_sum = np.sum(exp_qubits)
    
    for fragment, exp_val in zip(vcs, exp_qubits):
        allocated_shots = int(exp_val / exp_sum * tot_shots)
        vcs_shots.append((fragment, allocated_shots))
    
    return vcs_shots