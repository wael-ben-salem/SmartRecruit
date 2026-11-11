"""Run the whole pipeline in Python (same steps as the n8n workflow), for tests and debugging.

    python -m smartrecruit.pipeline data/samples/job_offer_data_engineer.txt data/samples/cv_*.pdf
"""
import sys
from concurrent.futures import ThreadPoolExecutor

from . import steps


def run(job_file: str, cv_files: list[str]) -> dict:
    return run_existing(steps.new_run(job_file, cv_files)["run_id"])


def run_existing(run_id: str) -> dict:
    cids = steps.store.candidates(run_id)

    def prepare_cv(cid: str):
        steps.read(run_id, cid)
        steps.anonymize(run_id, cid)
        steps.cv(run_id, cid)
        steps.index(run_id, cid)

    # same parallelism as in n8n: the job branch and the CV branches run side by side
    with ThreadPoolExecutor(max_workers=4) as pool:
        job_future = pool.submit(lambda: (steps.read(run_id, "job"), steps.job(run_id)))
        list(pool.map(prepare_cv, cids))
        job_future.result()
        list(pool.map(lambda cid: (steps.match(run_id, cid), steps.audit(run_id, cid)), cids))
    return steps.build_report(run_id)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: python -m smartrecruit.pipeline <job_offer> <cv1.pdf> [cv2.pdf ...]")
    result = run(sys.argv[1], sys.argv[2:])
    for r in result["ranking"]:
        print(f'{r["candidate_id"]}: {r["score"]}/100, must-have {r["must_have_met"]}, unverified {r["unverified_claims"]}')
    print("Report:", result["report_path"])
