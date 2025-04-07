# Cut&Shoot
Cut&Shoot is a tool to execute quantum circuits by applying *circuit cutting* and *shot-wise distribution* in pipeline.
![Cut&Shoot pipeline](https://github.com/alebocci/cutshot/blob/main/cutnshoot.png?raw=true)

The pipeline consists of four main steps:
1. **Cut:** The original circuit is divided into smaller fragments using the chosen *cutting tool*. The tool outputs all possible fragment variations, which are then treated as standalone quantum circuits with their respective shot allocation determined by a custom *allocation policy*.
2. **Split:** The shots for each fragment variation are distributed across the target NISQ devices according to the selected *split policy*. The shots of each fragment variation are executed independently and concurrently on the target QPUs.
3. **Merge:** The execution results from the NISQ devices are merged to obtain the probability distribution for each fragment through the user-specified *merge policy*, which may differ from the *split policy*.
4. **Sew:** Finally, the probability distributions of the fragments are combined to reconstruct the original circuit's probability distribution.

## Installation
Cut&Shoot can be installed using poetry:
```bash
git clone [this repository]
cd cutshot
poetry install
poetry shell
```

## Usage
Cut&Shoot can be used as a command line tool or as a Python library. 

Inside the poetry environemnt and from the src folder, the command line tool can be used as following:
```bash
usage: main.py [-h] [--configfile CONFIGFILE] [--times] [--params] [--stats] [--output OUTPUT] [--verbose]

Pipeline to apply circuit cutting and shot-wise to a quantum circuit.

options:
  -h, --help            show this help message and exit
  --configfile CONFIGFILE, -c CONFIGFILE
                        Configuration file .ini.
  --times, -t           Times recorded in the output.
  --params, -p          Params given to the pipeline run. Printed in out.json without -o. Includes -t.
  --stats, -s           Intermediate stats of the pipeline run. Printed in out.json without -o. Includes -t.
  --output OUTPUT, -o OUTPUT
                        Specify the file name where print all the stats. Includes -p and -s.
  --verbose, -v         Includes debug prints to the standard output.
```

The following example shows how to use Cut&Shoot as a Python library:
```python
from cutnshot.src import cutnshot

cutnshot(
    circuit,
    observable_string,
    shots,
    provider_backend_couples,
    cut_strategy_module,
    shots_allocation_module, 
    sw_policy_module,
    input_flags = None,
    metadata = None
    )
```
passing the following parameters:
- `circuit`: the quantum circuit in QASM format.
- `observable_string`: a string representing the observable to measure.
- `provider_backend_couple`: a list of tuples, each containing a provider and a backend.
- `shots`: the total number of shots.
- `cut_strategy_module`: the python module containing the cutting strategy which implements the cut strategy interface.
- `shots_allocation_module`: the python module containing the shots allocation module which implements the shots allocation strategy interface.
- `sw_policy_module`: the python module containing the shot-wise policies policy which implements the split and merge policy interfaces.
- `input_flags`: a dictionary containing the flags for formatting the logging and the output.
- `metadata`: a dictionary containing additional information that will be put in the output.

## External files
Cut&Shots needs a configuration file (e.g. conf.ini) in input which specifies the parameters of the pipeline. The configuration file is in .ini format and contains the following sections:
```ini
[SETTINGS]
circuit = path to the file containing the QASM circuit, e.g. "qasm_circuit.txt"
observables = string representing the observable, e.g. "ZXY"
shots = number of total shots of the run, e.g. 8000
backends = list of two element list [provider, backend] where the pipeline will execute the circuit [["ibm_aer", "aer.fake_brisbane"], ["ibm_aer", "aer.fake_kyoto"], ["ibm_aer", "aer.fake_osaka"]]
cut_strategy_module = name of the python script containg the cutting strategy, e.g. "pennylane_tool"
shots_allocation_module = name of the python script containg the shots allocation strategy, e.g. "policies.qubit_proportional"
sw_policy_module = name of the python script containg the shot-wise policies, e.g. "policies.sw_policies"
perf_exp_val = (optional) expected value of the circuit executed on a simulator without noiuse, e.g. 0
parallel = boolean flag that indicates if each execution on a backend is on a different process, values: True or False
metadata = (optional) data that will be copied in the output, must be JSON encodable, e.g. ["cutnshot","test2"]
```

The cutting strategy must be a Python script (e.g pennylane_tool.py), implementing the following interface:
```
- cut(circuit, observable_string) -> output, cut_data, cut_info
    circuit: QASM circuit to cut
    observable_string: observable to measure on the circuit
    output: list of tuples (fragment, observable) where fragment is a QASM circuit without basis changes and observable is a list of string representing the observables
    cut_data: dictionary containing data needed by the sew function
    cut_info: (optional) dictionary containing information about the cut recorded by the experiments, must be JSON serializable
- sew(qasm_obs_expvals, sew_data)  -> results
    qasm_obs_expvals: dictionary (fragment, observable) -> expected value, where (fragment , observable) are the tuples returned by the cut function and expected value is the expected value of the fragment execution
    sew_data: dictionary containing data needed by the sew function
    results: results of the sew function
```

The shots allocation strategy must be a Python script (e.g policies/qubit_proportional.py), implementing the following interface:
```
- allocate_shots: (vcs, shots_assignment) -> vc_shots
    vcs: list of qukit.VirtualCircuit circuit where each circuit has a metadata field containing the number of qubits
    shots_allocation: parameters for the allocation
    vcs_shots: list of tuples (fragment, shots), where fragment is a qukit.VirtualCircuit circuit and shots is the number of shots to assign to the fragment
```

The shot-wise policies must be a Python script (e.g policies/sw_policies.py), implementing the following interface:
```
- split(backends, shots) -> (dispatch, coefficients)
    backends: list of tuples (provider, backend)
    shots: number of shots to split
    dispatch: dictionary of dictionaries of integers, where dispatch[provider][backend] is the number of shots to send to the backend
    coefficients: dictionary of dictionaries of floats, where coefficients[provider][backend] is the weight of the backend in the policy
- merge(counts) -> (probs, coefficients)
    counts: dictionary of dictionaries of lists, where counts[provider][backend] is a list of tuples (circuit_id, observable, counts)
    probs: dictionary of dictionaries of floats, where probs[(circuit_id,observable)][state] is the probability of measuring the state in the circuit
    coefficients: dictionary of dictionaries of floats, where coefficients[provider][backend] is the weight of the backend in the policy
```
## OUTPUT

The simple output of the tool execution resume the pipeline steps and finally, the circuit expected value and its error are printed.
For example:

```
INFO:cutnshot:Expected value: 0.011723999999999983
INFO:cutnshot:Error: -0.011723999999999983
```

When the `--output` flag is used, the output is saved in a JSON file. The output contains the following fields:

- **`results`**: Final estimated result of the quantum computation (e.g., an observable's expectation value).

- **`times`**: Execution time breakdown (in seconds) for various pipeline stages:
  - `time_cutting`: Time spent splitting the circuit.
  - `time_allocation`: Time spent allocating shots.
  - `time_dispatch`: Time spent dispatching circuits to simulators.
  - `time_execution`: Time for actual quantum circuit execution.
  - `time_counts`: Time to collect and process measurement results.
  - `time_execution_retries`: Time spent retrying failed executions.
  - `time_merge`: Time to merge subcircuit results.
  - `time_expected_values`: Time to compute expected values.
  - `time_sew`: Time spent sewing together partial results.
  - `time_total`: Total pipeline execution time.

#### `header`

Metadata describing the simulation and execution configuration:

- **`observable`**: The quantum observable being measured (e.g., `"XZY"`).
- **`shots`**: Number of measurement shots per circuit.
- **`cut_tool`**: Name of the tool used for circuit cutting.
- **`shots_allocation`**: Policy used to distribute shots among subcircuits.
- **`provider_backend_couples`**: List of (provider, backend) pairs used (e.g., `["ibm_aer", "aer.fake_kyoto"]`).
- **`shot_wise_policies`**: Path or reference to the policy managing shot-wise execution.
- **`metadata`**:
  - `times_flag`: Whether timing was collected.
  - `stats_flag`: Whether statistics were collected.
  - `verbose`: Enables detailed logging if `true`.

#### `stats`

Detailed statistics and intermediate data collected during the run:

- **`cut_info`**: Info about circuit fragmentation:
  - `num_fragments`: Number of fragments.
  - `fragments_qubits`: Qubit count per fragment.
  - `num_variations`: Total number of basis variations.
  - `variations`: Number of variations per fragment.

- **`cut_output`**: List of `[QASM, basis]` pairs for each fragment.

- **`dispatch`**: Maps providers/backends to the dispatched subcircuits and their shot counts.

- **`counts`**: Raw measurement outcomes for each backend and basis.

- **`probs`**: Normalized probabilities from `counts`.

- **`split_coefficients`** and **`merge_coefficients`**: Weights used to distribute and combine results across multiple backends.

An example of JSON output is
```json
{
    "results": {
        "expected_value": 0.011723999999999983,
        "error": -0.011723999999999983
    },
    "times": {
        "time_cutting": 0.123456,
        "time_allocation": 0.234567,
        "time_dispatch": 0.345678,
        "time_execution": 0.456789,
        "time_counts": 0.567890,
        "time_execution_retries": 0.678901,
        "time_merge": 0.789012,
        "time_expected_values": 0.890123,
        "time_sew": 1.012345,
        "time_total": 1.123456
    },
    "header": {
        "observable": "XZY",
        "shots": 8000,
        "cut_tool": "pennylane_tool",
        "shots_allocation": "policies.qubit_proportional",
        "provider_backend_couples": [
            ["ibm_aer", "aer.fake_brisbane"],
            ["ibm_aer", "aer.fake_kyoto"],
            ["ibm_aer", "aer.fake_osaka"]
        ],
        "shot_wise_policies": ["policies.sw_policies"],
        "metadata": {
            "times_flag": true,
            "stats_flag": true,
            "verbose": false
        }
    },
    ...
}
```