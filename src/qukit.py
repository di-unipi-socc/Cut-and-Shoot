import threading, json
from typing import Any, Optional
from qiskit import QuantumCircuit  # type: ignore
from qiskit_aer import AerProvider, AerSimulator  # type: ignore
from qiskit_aer.noise import NoiseModel  # type: ignore
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2  # type: ignore
from qiskit_ibm_runtime.fake_provider import FakeProviderForBackendV2  # type: ignore
from qiskit_ibm_runtime.fake_provider.fake_backend import FakeBackendV2  # type: ignore


class ThreadWithReturnValue(threading.Thread):
    """Thread class with a return value.

    This class is a subclass of threading.Thread that allows the target function to return a value.

    Parameters
        ----------
        group : None
            The group.
        target : None
            The target function.
        name : None
            The name.
        args : tuple
            The arguments.
        kwargs : dict
            The keyword arguments.
        daemon : None
            The daemon.
        throw_exc : bool
            Whether to throw exceptions.
    """

    maximumNumberOfRuningThreads: Optional[int] = None

    def __init__(  # type: ignore  # pylint: disable=too-many-arguments
        self, group=None, target=None, name=None, args=(), kwargs=None, daemon=None, throw_exc=True
    ) -> None:
        """Initialize the thread.

        Parameters
        ----------
        group : None
            The group.
        target : None
            The target function.
        name : None
            The name.
        args : tuple
            The arguments.
        kwargs : dict
            The keyword arguments.
        daemon : None
            The daemon.
        throw_exc : bool
            Whether to throw exceptions.
        """

        if kwargs is None:
            kwargs = {}
        self._target = None

        threading.Thread.__init__(self, group, target, name, args, kwargs, daemon=daemon)
        self._return = None
        self._throw_exc = throw_exc
        self._exc = None

        self._thread_limiter: Optional[threading.Semaphore] = None
        if ThreadWithReturnValue.maximumNumberOfRuningThreads is not None:
            self._thread_limiter = threading.Semaphore(ThreadWithReturnValue.maximumNumberOfRuningThreads)

    def run(self) -> None:
        """Run the target function."""
        if self._target is not None:

            if self._thread_limiter is not None:
                self._thread_limiter.acquire()  # pylint: disable=consider-using-with

            try:
                self._return = self._target(*self._args, **self._kwargs)
            except Exception as e:  # pylint: disable=broad-except
                self._exc = e

            if self._thread_limiter is not None:
                self._thread_limiter.release()

            if self._throw_exc and self._exc is not None:
                raise self._exc

    def join(self, *args: Any) -> Any:
        """Join the thread.

        Parameters
        ----------
        *args : Any
            The arguments.

        Returns
        -------
        Any
            The return value.
        """
        threading.Thread.join(self, *args)
        return self._return

    @property
    def result(self) -> Any:
        """Return the result.

        Returns
        -------
        Any
            The return value.
        """
        return self._return

    @property
    def exception(self) -> Optional[Exception]:
        """Return the exception.

        Returns
        -------
        Optional[Exception]
            The exception.
        """
        return self._exc

class VirtualCircuit:
    
    def __init__(self, circuit, metadata = {}):
        self.circuit = circuit
        self.metadata = metadata.copy()
    def to_dict(self):
        return {
            "circuit": self.circuit,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(circuit=data["circuit"], metadata=data["metadata"])
    
    def describe(self):
        d = {}
        qc = QuantumCircuit.from_qasm_str(self.circuit)
        
        d["qubits"] = qc.num_qubits
        d["depth"] = qc.depth()
        d["num_gates"] = qc.size()
        
        d["2q_depth"] = qc.depth(filter_function=lambda x: x.operation.num_qubits == 2)
        
        d['num_1q_gates'] = sum(1 for op in qc.data if op.operation.num_qubits == 1)
        d['num_2q_gates'] = sum(1 for op in qc.data if op.operation.num_qubits == 2)
        d['num_measurements'] = sum(1 for op in qc.data if op.operation.name == 'measure')
        
        d["gates"] = dict(qc.count_ops())
        
        return d.copy()
        
        
class Job:
    def __init__(self, backend, results):
        self.backend = backend
        self.results = results
    
    def to_dict(self):
        return {
            "backend": str(self.backend),
            "results": [result.to_dict() for result in self.results],
        }

    @classmethod
    def from_dict(cls, data):
        results = [Result.from_dict(result) for result in data["results"]]
        return cls(backend=data["backend"], results=results)
        
class Result:
    def __init__(self, circuit, counts):
        self.circuit = circuit
        self.counts = counts

    def to_dict(self):
        return {
            "circuit": self.circuit,
            "counts": self.counts,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(circuit=data["circuit"], counts=data["counts"])

class QukitJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Job):
            return obj.to_dict()
        if isinstance(obj, Result):
            return obj.to_dict()
        if isinstance(obj, VirtualCircuit):
            return obj.to_dict()
        return super().default(obj)
    
    @staticmethod
    def decode(data):
        """Custom decoder to handle Job and Result objects."""
        if isinstance(data, dict) and "backend" in data and "results" in data:
            return Job.from_dict(data)
        if isinstance(data, dict) and "circuit" in data and "metadata" in data:
            return VirtualCircuit.from_dict(data)
        return data

def run_circuits_on_backend(backend, circuits):
    results = []
    for circuit,shots in circuits:
        qc = QuantumCircuit.from_qasm_str(circuit.circuit)
        result = backend.run(qc, shots=shots).result()
        results.append(Job(backend, [Result(circuit, result.get_counts())]))
        
    return results
    
class Dispatcher:
    
    def _get_backend(self, provider, backend):
        if provider == "ibm_aer":
            if backend.startswith("aer.fake"):
                return AerSimulator(noise_model=NoiseModel.from_backend(FakeProviderForBackendV2().backend(backend[4:])))
            if backend == "aer.perfect":
                return AerSimulator()
            
        raise ValueError(f"Backend {backend} not supported for provider {provider}. Please send a message to Giuseppe to add it, but only if you think it is very, very important to have it. Capito Ale?!")
    
    def run(self, dispatch):
        threads = {}
        for provider in dispatch:
            if provider not in threads:
                threads[provider] = {}
            for backend in dispatch[provider]:
                
                _backend = self._get_backend(provider, backend)
                
                if _backend is None:
                    raise ValueError(f"Backend {backend} not supported for provider {provider}")
                
                threads[provider][backend] = ThreadWithReturnValue(target=run_circuits_on_backend, args=(_backend, dispatch[provider][backend]))
                threads[provider][backend].start()
                
        results = {}
        for provider in threads:
            if provider not in results:
                results[provider] = {}
            for backend in threads[provider]:
                results[provider][backend] = threads[provider][backend].join()
                
        return results
                    