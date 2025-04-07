import hashlib
from qukit import VirtualCircuit
from pennylane import qml
from time import process_time


def hash_circuit(qasm):
    return str(hashlib.md5(qasm.encode()).hexdigest())

def string_to_qml_pauli_word(observable):
    qubits = list(range(len(observable)))
    obs = qml.pauli.string_to_pauli_word(observable[0])
    for q in qubits[1:]:
        if observable[q] == 'X':
            obs = obs @ qml.PauliX(q)
        elif observable[q] == 'Y':
            obs = obs @ qml.PauliY(q)
        elif observable[q] == 'Z':
            obs = obs @ qml.PauliZ(q)
        elif observable[q] == 'I':
            obs = obs @ qml.Identity(q)
        else:
            raise ValueError(f"Invalid observable {observable[q]}(q{q})")
    return obs

def expected_values(probs, vcs, old_vcs):
    results = {}
    for vc in vcs:
        circuit_id = vc.metadata["circuit_name"]
        observable = vc.metadata["observable"]
        expected_value = compute_expected_value(probs[(circuit_id,observable)], observable)
        old_circuit = old_vcs[circuit_id]
        results[(old_circuit, observable)] = expected_value
    return results

def compute_expected_value(probabilities, observable):
    expected_value = 0
    eigvals = qml.eigvals(string_to_qml_pauli_word(observable))
    for state, probability in probabilities.items():
        state_index = int(state, 2)
        expected_value += probability * eigvals[state_index]   
    return expected_value.real

def qasm_to_pennylane(qasm: str):
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

def push_obs(virtual_circuit):
    qasm_circuit = virtual_circuit.circuit
    observable_string = virtual_circuit.metadata["observable"]
    num_qubits = virtual_circuit.metadata["qubits"]
    penny_circuit = qasm_to_pennylane(qasm_circuit)
    def fun():
        penny_circuit()
        return qml.expval(qml.pauli.string_to_pauli_word(observable_string))
    qs = qml.tape.make_qscript(fun)()
    circuit_name = str(hash_circuit(qasm_circuit))
    metadata = {"circuit_name":circuit_name, "observable": observable_string, "qubits": num_qubits}
    vc = VirtualCircuit(pennylane_to_qasm(qs), metadata)
    return vc

def fragments_to_vc(cut_output):
    vcs = []
    for fragment, observable in cut_output:
        for obs in observable:
            qubits = len(obs)
            hash = hash_circuit(fragment)
            metadata = {
                "circuit_name": hash,
                "qubits": qubits,
                "observable": obs
                }
            vcs.append(VirtualCircuit(fragment, metadata))
    return vcs

def create_single_dispatch(dispatch, fragment,provider, backend, shots):
    if provider not in dispatch:
        dispatch[provider] = {}
    if backend not in dispatch[provider]:
        dispatch[provider][backend] = []
    dispatch[provider][backend].append((fragment, shots))
    return dispatch
 
def create_dispatch(vcs_shots, provider_backend_couples, split_fun):
    dispatch = {}
    #splitted_coefficients_list = [] #TODO sembra che i coefficienti siano uguali per i frammenti, togliere?
    for fragment, shots in vcs_shots:
        splitted, splitted_coefficients = split_fun(provider_backend_couples, shots)
        #splitted_coefficients_list.append((fragment.metadata["circuit_name"], splitted_coefficients))
        for provider, backend, split_shots in splitted:
            dispatch = create_single_dispatch(dispatch, fragment, provider, backend, split_shots)
    return dispatch, splitted_coefficients

def results_to_counts(results_dispatcher):
    try:
        counts_dispatcher = {}
        for provider in results_dispatcher:
            counts_dispatcher[provider] = {}
            for backend in results_dispatcher[provider]:
                counts_dispatcher[provider][backend] = []
                for job in results_dispatcher[provider][backend]:
                    result = job.results[0] 
                    circuit_id = result.circuit.metadata["circuit_name"]
                    observable = result.circuit.metadata["observable"] #TODO occhio se cambia
                    # _counts = json.loads(json.dumps(result.counts[list(result.counts.keys())[0]]))
                    counts = {k[::-1]:v for k,v in result.counts.items()} #TODO: verify endianness for each provider
                    counts_dispatcher[provider][backend].append((circuit_id,observable,counts))  
        return counts_dispatcher
    except AttributeError as e:
        if "'NoneType' object has no attribute 'results'" in repr(e):
            print("IBM ha fallito, rilancio l'esecuzione.")
            return None
        raise e
def record_time(times, name, start):
    end = process_time()
    times[name] = (end - start) #in seconds
    return times
