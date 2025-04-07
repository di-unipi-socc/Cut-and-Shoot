
import logging, cutnshot, json, configparser, importlib, os
from utils import hash_circuit
from argparse import ArgumentParser
from os.path import join, dirname
from dotenv import load_dotenv


def main():

    dotenv_path = join(dirname(__file__), '.env')
    load_dotenv(dotenv_path)
    # create logger
    logger = logging.getLogger("cutnshot")
    logging.basicConfig(level=logging.ERROR)
    logger.setLevel(logging.INFO)
    
    parser = ArgumentParser(prog='cutnshot.py',
                        description='Pipeline to apply circuit cutting and shot-wise to a quantum circuit.')
    parser.add_argument('--configfile', '-c', type=str, help='Configuration file .ini.',  default="config.ini")
    parser.add_argument('--times', '-t', help='Times recorded in the output.', action='store_true')
    parser.add_argument('--params', '-p', help='Params given to the pipeline run. Printed in out.json without -o. Includes -t.', action='store_true')
    parser.add_argument('--stats', '-s', help='Intermediate stats of the pipeline run. Printed in out.json without -o. Includes -t.', action='store_true')
    parser.add_argument('--output', '-o', help='Specify the file name where print all the stats. Includes -p and -s.', default=None)
    parser.add_argument('--verbose', '-v', help='Verbose mode for the output.', action='store_true')
    
    args = parser.parse_args()

    input_flags = {}
    times_flag = args.times
    params_flag = args.params
    stats_flag = args.stats
    output_file = args.output
    if output_file:
        times_flag = True
        stats_flag = True
        params_flag = True
    if stats_flag:
        times_flag = True
    if params_flag:
        times_flag = True
    input_flags["times_flag"] = times_flag
    input_flags["params_flag"] = params_flag
    input_flags["stats_flag"] = stats_flag
    input_flags["verbose"] = args.verbose

    # Load configuration file
    config_file = args.configfile
    config = configparser.ConfigParser()
    config.read(config_file)
    
    settings = config["SETTINGS"]
    circuit_name = settings["circuit_name"]
    n_qubits = settings["n_qubits"]
    shots = int(json.loads(config["SETTINGS"]["shots"]))
    observable_string = json.loads(config["SETTINGS"]["observables"])
    input_flags["parallel_execution_flag"] = False if not config["SETTINGS"]["parallel_execution"] or config["SETTINGS"]["parallel_execution"] != "True" else True

    circuit_file = json.loads(config["SETTINGS"]["circuit"])
    path = os.path.join(os.path.dirname(__file__), circuit_file)
    with open(path, "r") as f:
        circuit_qasm = f.read()

    provider_backend_couples = json.loads(config["SETTINGS"]["backends"])

    cut_strategy = json.loads(config["SETTINGS"]["cut_strategy_module"])
    cut_strategy_module = importlib.import_module(cut_strategy)
    

    shotwise_policy = json.loads(config["SETTINGS"]["sw_policy_module"])
    sw_policy_module = importlib.import_module(shotwise_policy)
    
    shots_allocation_name = json.loads(config["SETTINGS"]["shots_allocation_module"])
    shots_allocation_module = importlib.import_module(shots_allocation_name)

    result = cutnshot.cutnshot(
        circuit_qasm,
        observable_string,
        shots,
        provider_backend_couples,
        cut_strategy_module,
        shots_allocation_module,
        sw_policy_module,
        input_flags
    )
    logger.info(f"Expected value: {result['results']}")

    if params_flag:
        result["params"]["circuit_name"] = circuit_name.replace('\"', "")
        result["params"]["n_qubits"] = n_qubits

    if "perf_exp_val" in config["SETTINGS"]:
        perf_exp_val = float(json.loads(config["SETTINGS"]["perf_exp_val"]))
        error = perf_exp_val-result["results"]
        if params_flag:
            result["params"]["perf_exp_val"] = perf_exp_val
        result["error"] = error

        logger.info(f"Error: {error}")

    if output_file or stats_flag:
        dispatch = result["stats"]["dispatch"]
        new_dispatch = {} #make it json serializable
        for provider in dispatch:
            for backend in dispatch[provider]:
                if provider not in new_dispatch:
                    new_dispatch[provider] = {}
                if backend not in new_dispatch[provider]:
                    new_dispatch[provider][backend] = []
                for frag, shots in dispatch[provider][backend]:
                    new_dispatch[provider][backend].append((frag.circuit, shots))
        result["stats"]["dispatch"] = new_dispatch

        probs = result["stats"]["probs"]
        new_probs = {}
        for k in probs:
            new_probs[str(k)] = probs[k]
        result["stats"]["probs"] = new_probs

        qasm_obs_exp_values = result["stats"]["exp_values"]
        exp_vals = {}
        for qasm, obs in qasm_obs_exp_values:
            hash = hash_circuit(qasm)
            exp_vals[str((hash,obs))] = qasm_obs_exp_values[(qasm, obs)]
        result["stats"]["exp_values"] = exp_vals

    if output_file:
        with open(os.path.join(os.path.dirname(__file__), output_file), "w") as f:
            json.dump(result, f)
    elif stats_flag:
        with open("out.json", "w") as f:
            json.dump(result, f)

if __name__ == "__main__":
    main()