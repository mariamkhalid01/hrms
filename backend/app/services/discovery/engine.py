"""Actual PM4Py discovery, independently applied to every uploaded process partition."""

import logging
from collections import Counter, defaultdict

import pandas as pd
import pm4py
from pm4py.objects.log.obj import EventLog

from app.core.config import Settings
from app.schemas.discovery import DiscoveryRequest, ProcessModel
from app.services.discovery.log import (
    build_log,
    distribution,
    prepare_frame,
    stable_id,
    state_counts,
)
from app.services.discovery.serialization import (
    flow_model,
    graph_components,
    serialize_petri,
    serialize_tree,
)
from app.services.process_separation.separator import split_processes
from app.services.variants.engine import discover_variants


def inductive_model(log, options: DiscoveryRequest, settings: Settings) -> dict:
    eligible = EventLog(
        [
            trace
            for trace in log
            if trace.attributes["case_state"] not in {"incomplete", "cancelled"}
        ]
    )
    base = {
        "status": "skipped",
        "reason": None,
        "input_case_count": len(eligible),
        "excluded_case_count": len(log) - len(eligible),
        "noise_threshold": options.noise_threshold,
    }
    reason = None
    if options.algorithm == "dfg":
        reason = "DFG-only discovery requested."
    elif not eligible:
        reason = "No eligible cases remain after excluding known incomplete and cancelled cases."
    elif options.algorithm == "auto" and len(eligible) < 2:
        reason = "Auto mode requires at least two eligible cases for Inductive Miner."
    elif not any(len(trace) > 1 for trace in eligible):
        reason = "Only single-event cases are available; the DFG represents the observations."
    elif sum(map(len, eligible)) > settings.inductive_max_events:
        reason = "Eligible event count exceeds the configured Inductive Miner limit."
    elif len({event["concept:name"] for trace in eligible for event in trace}) > (
        settings.inductive_max_activities
    ):
        reason = "Activity count exceeds the configured Inductive Miner limit."
    if reason:
        return {**base, "reason": reason}
    try:
        tree = pm4py.discover_process_tree_inductive(
            eligible, noise_threshold=options.noise_threshold, multi_processing=False
        )
        net, initial, final = pm4py.convert_to_petri_net(tree)
        return {**base, "status": "discovered", "_tree": tree, "_net": (net, initial, final)}
    except Exception:
        # DFG and exact variants remain usable; failures are explicit, never fabricated.
        logging.getLogger("hr_process_mining").exception("Inductive discovery failed")
        return {
            **base,
            "status": "failed",
            "reason": "Inductive Miner could not build this model. DFG and variants are available.",
        }


def discover_process(
    frame: pd.DataFrame, process: str, options: DiscoveryRequest, settings: Settings
) -> tuple[dict, list[dict]]:
    log, cases = build_log(frame, options)
    dfg, starts, ends = pm4py.discover_dfg(log)
    frequencies, case_frequencies, repeated = Counter(), Counter(), Counter()
    edge_cases = Counter()
    service, elapsed, gaps = defaultdict(list), defaultdict(list), defaultdict(list)
    repeated_cases = 0
    for case in cases:
        counts = Counter(record["activity"] for record in case.records)
        frequencies.update(counts)
        case_frequencies.update(counts.keys())
        repeated.update(label for label, count in counts.items() if count > 1)
        repeated_cases += any(count > 1 for count in counts.values())
        pairs = set()
        for record in case.records:
            start, end = record.get("activity_start"), record.get("activity_end")
            if pd.notna(start) and pd.notna(end):
                service[record["activity"]].append((end - start).total_seconds())
        for left, right in zip(case.records, case.records[1:], strict=False):
            pair = (left["activity"], right["activity"])
            pairs.add(pair)
            elapsed[pair].append((right["timestamp"] - left["timestamp"]).total_seconds())
            end, start = left.get("activity_end"), right.get("activity_start")
            if pd.notna(end) and pd.notna(start):
                gaps[pair].append((start - end).total_seconds())
        edge_cases.update(pairs)
    activity_ids = {label: stable_id("activity", process, label) for label in sorted(frequencies)}
    components = graph_components(list(activity_ids), list(dfg))
    membership = {label: index for index, group in enumerate(components) for label in group}
    activities = [
        {
            "id": activity_ids[label],
            "label": label,
            "frequency": frequencies[label],
            "case_frequency": case_frequencies[label],
            "repeated_case_count": repeated[label],
            "start_frequency": int(starts.get(label, 0)),
            "end_frequency": int(ends.get(label, 0)),
            "service_time_seconds": distribution(service[label]),
        }
        for label in activity_ids
    ]
    transitions = []
    for (source, target), frequency in sorted(dfg.items()):
        pair = (source, target)
        transitions.append(
            {
                "id": stable_id("edge", process, source, target),
                "source": activity_ids[source],
                "target": activity_ids[target],
                "frequency": int(frequency),
                "case_frequency": edge_cases[pair],
                "is_self_loop": source == target,
                "in_graph_cycle": membership[source] == membership[target],
                "elapsed_time_seconds": distribution(elapsed[pair]),
                "inter_activity_gap_seconds": distribution(gaps[pair]),
                "overlap_count": sum(value < 0 for value in gaps[pair]),
            }
        )
    outgoing = defaultdict(list)
    for edge in transitions:
        outgoing[edge["source"]].append(edge)
    alternatives = []
    for source, edges in sorted(outgoing.items()):
        if len(edges) < 2:
            continue
        total = sum(edge["frequency"] for edge in edges)
        alternatives.append(
            {
                "source": source,
                "choices": [
                    {
                        "target": edge["target"],
                        "frequency": edge["frequency"],
                        "outgoing_percentage": 100 * edge["frequency"] / total,
                    }
                    for edge in edges
                ],
            }
        )
    cyclic_edges = defaultdict(list)
    id_membership = {activity_ids[label]: index for label, index in membership.items()}
    for edge in transitions:
        if edge["in_graph_cycle"]:
            cyclic_edges[id_membership[edge["source"]]].append(edge["id"])
    loops = []
    for index, group in enumerate(components):
        if len(group) > 1 or (group[0], group[0]) in dfg:
            ids = {activity_ids[label] for label in group}
            loops.append(
                {
                    "activity_ids": sorted(ids),
                    "transition_ids": cyclic_edges[index],
                }
            )
    variants = discover_variants(log, cases, process)
    inductive = inductive_model(log, options, settings)
    if inductive["status"] == "discovered":
        inductive["process_tree"] = serialize_tree(inductive.pop("_tree"), process)
        inductive["petri_net"] = serialize_petri(*inductive.pop("_net"), process)
    warnings = [
        "DFG branches and cycles describe adjacency, not proven choice or concurrency.",
        "Inductive models may generalize beyond traces; Petri arcs have no observed frequency.",
    ]
    counts = state_counts(cases)
    if counts["unknown"]:
        warnings.append(
            "Case completion is unknown for some cases. Endpoints are observed boundaries, "
            "and Inductive Miner treats these observed traces as complete examples."
        )
    if any(case.status_conflict for case in cases):
        warnings.append("Conflicting case-status values were classified as unknown.")
    if options.noise_threshold:
        warnings.append(
            "Noise filtering affects only Inductive Miner; the DFG and variants remain exact."
        )
    if inductive["status"] == "failed":
        warnings.append(inductive["reason"])
    model = {
        "id": stable_id("process", process),
        "name": process,
        "event_count": len(frame),
        "case_count": len(cases),
        "variant_count": len(variants),
        "activities": activities,
        "transitions": transitions,
        "start_activities": [
            {"activity_id": activity_ids[label], "frequency": int(count)}
            for label, count in sorted(starts.items())
        ],
        "end_activities": [
            {"activity_id": activity_ids[label], "frequency": int(count)}
            for label, count in sorted(ends.items())
        ],
        "alternative_paths": alternatives,
        "loops": loops,
        "react_flow": flow_model(activities, transitions),
        "inductive": inductive,
        "metadata": {
            "boundary_semantics": "Observed endpoints, including incomplete/cancelled cases.",
            "duration_semantics": "UTC wall-clock seconds; duration is last minus first observed "
            "timestamp. Signed interval gaps can be negative for overlapping work.",
            "ordering": ["timestamp", "event_order", "source_row"],
            "duplicate_policy": "Retain every validated event, including acknowledged duplicates.",
            "case_status_attribute": options.case_status_attribute,
            "case_status_counts": counts,
            "conflicting_status_case_count": sum(case.status_conflict for case in cases),
            "unrecognized_status_case_count": sum(case.status_unrecognized for case in cases),
            "repeated_case_count": repeated_cases,
            "warnings": warnings,
        },
    }
    return ProcessModel.model_validate(model).model_dump(), variants


def discover(
    frame: pd.DataFrame, options: DiscoveryRequest, settings: Settings
) -> tuple[list, dict]:
    prepared = prepare_frame(frame, options)
    models, variants = [], {}
    for process, partition in split_processes(prepared):
        model, sequences = discover_process(partition, str(process), options, settings)
        models.append(model)
        variants[model["id"]] = sequences
    return models, variants
