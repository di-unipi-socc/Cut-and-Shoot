'''
This file implements the function of the cutting tool.
The cutting tool must implement the following functions:
    - cut: cut(circuit, observable_string) -> output, cut_data, cut_info
        circuit: QASM circuit to cut
        observable_string: observable to measure on the circuit
        output: list of tuples (fragment, observable) where fragment is a QASM circuit without basis changes and observable is a list of string representing the observables
        cut_data: dictionary containing data needed by the sew function
        cut_info: dictionary containing information about the cut recorded by the experiments (can be None)
    - sew: sew(qasm_obs_expvals, sew_data)  -> results
        qasm_obs_expvals: dictionary (fragment, observable) -> expected value, where (fragment , observable) are the tuples returned by the cut function and expected value is the expected value of the fragment execution
        sew_data: dictionary containing data needed by the sew function
        results: results of the sew function
'''

from pennylane import qml
from typing import Any, Optional, Callable
import hashlib

def cut(circuit, observable_string):
    tapes, communication_graph, prepare_nodes, measure_nodes, cut_info = pennylane_cut(circuit, observable_string)    
    #output, tapes_info = tapes_to_vc(tapes_len)
    output, tapes_info = tapes_to_qasm(tapes)
    sew_data = {"tapes_info": tapes_info,"communication_graph": communication_graph, "prepare_nodes": prepare_nodes, "measure_nodes": measure_nodes}
    return output, sew_data, cut_info

def sew(qasm_obs_expvals, sew_data):
    tapes_info = sew_data["tapes_info"]
    communication_graph = sew_data["communication_graph"]
    prepare_nodes = sew_data["prepare_nodes"]
    measure_nodes = sew_data["measure_nodes"]

    _exp_vals = []
    for tape in tapes_info:
        _sub_exp_vals = []
        for frag, obs in tape:
            _sub_exp_vals.append(qasm_obs_expvals[(frag,obs)])
        _exp_vals.append(_sub_exp_vals)
    exp_vals = []
    for e in _exp_vals:
        if len(e) > 1:
            exp_vals.append(tuple(e))
        else:
            exp_vals.append(e[0])
   
    r = qml.qcut.qcut_processing_fn(
        exp_vals,
        communication_graph,
        prepare_nodes,
        measure_nodes,
    )
    return r

def get_cut_params(circuit):
    circuit_qubits = circuit.num_wires
    cut_params = {
        "max_free_wires": circuit_qubits-1,"min_free_wires": 2,
        "num_fragments_probed":(2, circuit_qubits//2+1)
    }
    return cut_params

def hash_circuit(qasm):
    return str(hashlib.md5(qasm.encode()).hexdigest())

def qasm_to_pennylane(qasm: str) -> Callable:
    qasm_circuit = qml.from_qasm(qasm)
    def fun():
        qasm_circuit()
    return fun
def pennylane_to_qasm(circuit: qml.QNode) -> str:
    if hasattr(circuit, "tape"):
        c = circuit.tape.to_openqasm()
        
    else:
        c= circuit.to_openqasm()
    return c

def tapes_to_vc(tapes):
    qasm_fragments = []
    tapes_info = []
    for tape, tape_qubits in tapes:
        frag_list = []
        for expval in tape.measurements:
            _tape = qml.tape.QuantumTape(ops=tape.operations, measurements=[expval])
            _frag = pennylane_to_qasm(_tape)
            qasm_fragments.append((_frag, qml.pauli.pauli_word_to_string(_tape.observables[0]),tape_qubits))
            frag_list.append((_tape, hash_circuit(_frag)))
        tapes_info.append(frag_list)
    return qasm_fragments, tapes_info

def tapes_to_qasm(tapes):
    qasm_fragments = []
    tapes_info = []
    for tape in tapes:
        frag_list = []
        observables = []
        qasm = pennylane_to_qasm(tape)
        for expval in tape.measurements:
            obs = qml.pauli.pauli_word_to_string(expval.obs)
            frag_list.append((qasm, obs))
            observables.append(obs)
        tapes_info.append(frag_list)
        qasm_fragments.append((qasm, observables))
    return qasm_fragments, tapes_info

def pennylane_cut(circuit, observables):
    cut_info = {}
    obs =  [qml.expval(qml.pauli.string_to_pauli_word(observables))]
    penny_circ = qasm_to_pennylane(circuit)
    qs = qml.tape.make_qscript(penny_circ)()
    ops= qs.operations
    
    cut_params = get_cut_params(qs)

    uncut_tape = qml.tape.QuantumTape(ops, obs)

    #Se ci sono i num_fragments, si usano, altrimenti si usa la strategia
    graph = qml.qcut.tape_to_graph(uncut_tape)
    if 'num_fragments' in cut_params:
        cut_graph = qml.qcut.find_and_place_cuts(
            graph = graph,
            num_fragments=cut_params['num_fragments'],
        )
    else:
        cut_graph = qml.qcut.find_and_place_cuts(
            graph = qml.qcut.tape_to_graph(uncut_tape),
            cut_strategy = qml.qcut.CutStrategy(**cut_params),
        )

    qml.qcut.replace_wire_cut_nodes(cut_graph)
    fragments, communication_graph = qml.qcut.fragment_graph(cut_graph)
    fragment_tapes = [qml.qcut.graph_to_tape(f) for f in fragments]

    cut_info["num_fragments"] = len(fragment_tapes)

    cut_info["fragments_qubits"] = [len(tape.wires) for tape in fragment_tapes]
    # Creation of fragments varations
    expanded = [qml.qcut.expand_fragment_tape(t) for t in fragment_tapes]
    
    configurations = []
    prepare_nodes = []
    measure_nodes = []
    for tapes, p, m in expanded:
        configurations.append(tapes)
        prepare_nodes.append(p)
        measure_nodes.append(m)

    tapes = [tape for c in configurations for tape in c]

    num_variations = 0
    variatons = []
    for c in configurations:
        n = 0
        for tape in c:
            num_variations += len(tape.measurements)
            n += len(tape.measurements)
        variatons.append(n)
    cut_info["num_variations"] = num_variations
    cut_info["variations"] = variatons

    return tapes, communication_graph, prepare_nodes, measure_nodes, cut_info