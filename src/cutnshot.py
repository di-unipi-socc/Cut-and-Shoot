from qukit import Dispatcher, QukitJSONEncoder, VirtualCircuit
import logging, datetime, multiprocessing, json, os
from time import process_time, perf_counter
import utils as utils

TIME_CUTTING = "time_cutting"
TIME_ALLOCATION = "time_allocation"
TIME_DISPATCH = "time_dispatch"
TIME_EXECUTION = "time_execution"
TIME_SYNCHRONIZATION = "time_synchronization"
TIME_COUNTS = "time_counts"
TIME_SIMULATION = "time_simulation"
TIME_MERGE = "time_merge"
TIME_EXPECTED_VALUES = "time_expected_values"
TIME_SEW = "time_sew"
TIME_TOTAL = "time_total"
TIME_EXECUTION_RETRIES = "time_execution_retries"

# create logger
logger = logging.getLogger("cutnshot")
logging.basicConfig(level=logging.ERROR)
logger.setLevel(logging.INFO)

def single_execution(i,dispatch, string):
    dispatcher = Dispatcher()
    print(f"Executing a process as machine {string} "+datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    execution_results = dispatcher.run(dispatch)
    with open(f"./temp/{i}.json", "w") as f:
        json.dump(execution_results, f, cls=QukitJSONEncoder)

def parallel_execution(dispatch, times):
    processes = []
    if not os.path.exists("./temp"):
        os.makedirs("./temp")
    start = process_time()
    i=0
    for provider in dispatch:
        for backend in dispatch[provider]:
            arg = {provider: {backend: dispatch[provider][backend]}}
            string = f"{provider}_{backend}"
            p = multiprocessing.Process(target=single_execution, args=(i,arg,string))
            processes.append(p)
            p.start()
            i+=1
    for p in processes:
        p.join()
    
    times = utils.record_time(times, TIME_EXECUTION, start)

    single_res = {}
    start = process_time()
    for j in range(0,i):
        with open(f"./temp/{j}.json", "r") as f:
            dict = json.load(f, object_hook=QukitJSONEncoder.decode)
        for backend in dict:
            if backend not in single_res:
                single_res[backend] = {}
            single_res[backend].update(dict[backend])
        os.remove(f"./temp/{j}.json")

    times = utils.record_time(times, TIME_SYNCHRONIZATION, start)
    
    start = process_time()
    counts = utils.results_to_counts(single_res)
    times = utils.record_time(times, TIME_COUNTS, start)
    return counts, times


def cutnshot(
    circuit,
    observable_string,
    shots,
    provider_backend_couples,
    cut_strategy_module,
    shots_allocation_module, 
    sw_policy_module,
    input_flags = None,
    metadata = None
    ):
    if input_flags is None:
        times_flag = False
        stats_flag = False
        params_flag = False
        parallel_execution_flag = False
    else:
        times_flag = input_flags["times_flag"] if "times_flag" in input_flags else False
        stats_flag = input_flags["stats_flag"] if "stats_flag" in input_flags else False
        params_flag = input_flags["params_flag"] if "params_flag" in input_flags else False
        parallel_execution_flag = input_flags["parallel_execution_flag"] if "parallel_execution_flag" in input_flags else False
        if "verbose" in input_flags and input_flags["verbose"]:
            logger.setLevel(logging.DEBUG)

    times = {}

    logger.info("Starting Cut_and_Shot "+datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if "run" in input_flags:
        logger.debug(f"Circuit Name: {input_flags['run']['circuit']}")
        logger.debug(f"Qubit: {input_flags['run']['qubit']}")
    logger.debug(f"Observable: {observable_string}")
    logger.debug(f"Shots: {shots}")
    logger.debug(f"Cut Tool: {cut_strategy_module.__name__}")
    logger.debug(f"Shots Allocation: {shots_allocation_module.__name__}")
    logger.debug(f"Len Provider Backend Couple: {len(provider_backend_couples)}")
    logger.debug(f"Shot-wise Policy: {sw_policy_module.__name__}")
    logger.debug(f"Parallel Execution: {parallel_execution_flag}")
    logger.debug(f"Input Flags: {input_flags}")
    logger.debug(f"Metadata: {metadata}")

    
    initial_time = perf_counter()
    
    #cut
    logger.info(f"Cutting "+datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    start = process_time()
    cut_res = cut_strategy_module.cut(circuit, observable_string)
    if len(cut_res)==3:
        cut_output, sew_data, cut_info = cut_res
    else:
        cut_output, sew_data = cut_res
        cut_info = None
    times = utils.record_time(times, TIME_CUTTING, start)

    logger.debug(f"Cut info: {cut_info}")

    vcs = utils.fragments_to_vc(cut_output)

    new_vcs = []
    old_vcs = {}
    for vc in vcs:
        new_vc = utils.push_obs(vc)
        new_vcs.append(new_vc)

        new_name = new_vc.metadata["circuit_name"]
        old_vc = vc.circuit
        old_vcs[new_name] = old_vc
    vcs = new_vcs

    #Allocation of shots
    logger.info(f"Allocating shots "+datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    start = process_time()
    vcs_shots = shots_allocation_module.allocate_shots(vcs, shots)

    times = utils.record_time(times, TIME_ALLOCATION, start)

    #split
    logger.info(f"Splitting "+datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    start = process_time()
    dispatch, split_coefficients = utils.create_dispatch(vcs_shots, provider_backend_couples, sw_policy_module.split)
    times = utils.record_time(times, TIME_DISPATCH, start)

    if not parallel_execution_flag:
        #retry when IBM fails
        time_execution_retries = 0.0
        retry = True
        while(retry):
            dispatcher = Dispatcher()
            #Execute the dispatch
            logger.info(f"Executing "+datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))       
            start = process_time()
            execution_results = dispatcher.run(dispatch)
            times = utils.record_time(times, TIME_EXECUTION, start)

            #Counts calculation
            logger.info(f"Calculating counts "+datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            start = process_time()
            counts = utils.results_to_counts(execution_results)
            times = utils.record_time(times, TIME_COUNTS, start)
            if counts:
                retry = False
                times[TIME_EXECUTION_RETRIES] = time_execution_retries
            else:
                logger.info("IBM has filed :( restarting the execution at "+datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                time_execution_retries += times[TIME_EXECUTION]
    else:
        counts, times = parallel_execution(dispatch, times)

    #merge 
    logger.info(f"Merging "+datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    start = process_time()
    probs, merge_coefficients =sw_policy_module.merge(counts) #probs = {(circuit_id,obs): {state: probability}}
    times = utils.record_time(times, TIME_MERGE, start)
    
    #expected values
    logger.info(f"Expected values "+datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    start = process_time()
    
    qasm_obs_exp_values= utils.expected_values(probs, vcs, old_vcs)
    
    times = utils.record_time(times, TIME_EXPECTED_VALUES, start)

    #sew
    logger.info(f"Sewing "+datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    start = process_time()
    final_result = cut_strategy_module.sew(qasm_obs_exp_values, sew_data)
    times = utils.record_time(times, TIME_SEW, start)

    end_time = perf_counter()
    times[TIME_TOTAL] = end_time - initial_time

    results = {}



    if params_flag:
        results["params"] = {
            "circuits": circuit,
            "observable": observable_string,
            "shots": shots,
            "backends": provider_backend_couples,
            "cut_strategy": cut_strategy_module.__name__,
            "shots_allocation": shots_allocation_module.__name__,
            "shot_wise_policy": sw_policy_module.__name__,
            "operation": "cc_sw",
            "metadata": metadata
        }
    results["results"] = final_result

    if times_flag: 
        results["times"]=  times
    if stats_flag:

        vc = VirtualCircuit(circuit, {})
        #fragments stats in cut_output
        for i in range(len(cut_output)):
            circ, obs = cut_output[i]
            stats = vcs[i].describe()
            cut_output[i] = (circ, obs, stats)

        results["stats"] = {
            "circuit_stats": vc.describe(),
            "cut_info": cut_info,
            "cut_output": cut_output,
            "dispatch": dispatch,
            "counts": counts,
            "probs": probs,
            "split_coefficients": split_coefficients,
            "merge_coefficients": merge_coefficients,
            "exp_values": qasm_obs_exp_values,
        }


    return results