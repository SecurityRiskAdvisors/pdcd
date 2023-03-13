import concurrent.futures
from typing import List
from dataclasses import dataclass, field

from .routines import Routine


def routine_names(routines: List[Routine]):
    return [routine.name for routine in routines]


@dataclass
class JobBatch:
    routines: List[Routine]

    @property
    def names(self):
        return routine_names(routines=self.routines)


@dataclass
class JobHandler:
    # this class implements a very naive batching queue for jobs based on the
    # dependencies in the jobs
    # while the batching has a short circuit for cyclical dependencies, users should still
    #   make an effort to avoid cyclical references
    routines: List[Routine]
    workers: int = 2
    batches: List[JobBatch] = field(default_factory=list, init=False)

    def __post_init__(self):
        names = routine_names(routines=self.routines)
        if len(names) > len(list(set(names))):
            raise Exception("duplicate routine names")
        self.init_batches()
        self.validate_deps_exist()

    @property
    def names_in_current_batches(self) -> List[str]:
        return [name for batch in self.batches for name in batch.names]

    @property
    def all_routine_names(self) -> List[str]:
        return routine_names(routines=self.routines)

    def validate_deps_exist(self):
        all_dep_names = []
        [all_dep_names.extend(routine.dependencies) for routine in self.routines]
        if not set(all_dep_names).issubset(set(self.all_routine_names)):
            raise Exception("Dependency names do not match payload names")

    def process_next_batch(self):
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=self.workers)
        for routine in self.batches[0].routines:
            p = pool.submit(routine.run_ctr)
        pool.shutdown(wait=True)
        self.batches.pop(0)

    def init_batches(self):
        nodep_list = []
        dep_list = []
        # split routines into ones that have dependencies vs those that dont
        for routine in self.routines:
            (nodep_list if len(routine.dependencies) == 0 else dep_list).append(routine)
        # first batch is always the list of items without dependencies
        self.batches.append(JobBatch(routines=nodep_list))

        # loop over the remaining routines
        #   if any have all their deps met by an existing batch, add them to a new batch and
        #   remove them from the list
        # this should handle extrememly nested dependencies as long as they aren't cyclical
        loop_ct = 0
        while len(dep_list) != 0:
            # TODO: check that dependency actually exists or actually make a DAG
            if loop_ct > 100:
                raise Exception("Excessive nesting in dependencies")
            batch = JobBatch(routines=[])
            routines = dep_list.copy()
            for routine in routines:
                if all([dep in self.names_in_current_batches for dep in routine.dependencies]):
                    batch.routines.append(routine)
                    dep_list.remove(routine)

            self.batches.append(batch)
            loop_ct += 1

    def run(self):
        while len(self.batches) > 0:
            self.process_next_batch()

    def cleanup_routines(self):
        for routine in self.routines:
            routine.cleanup()
