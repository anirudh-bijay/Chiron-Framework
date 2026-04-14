# Dead-code elimination on SSA.

import sys
from collections import deque

import networkx as nx

from .basic_block import basic_block
from .label import label
from .operands import variable
from .renumber import src_variables
from .statements import (assignment_statement, jump_statement, pop_statement,
                         push_statement, statement, syscall_statement,
                         φ_statement)


def _get_defs(cfg: nx.DiGraph[label]) -> dict[variable, tuple[label, int]]:
    '''
    Get the definition sites of each variable in the CFG.

    :param networkx.DiGraph[label] cfg: The SSA CFG.
    :return dict[variable, set[tuple[label, int]]]: A dictionary mapping
        each variable to the set of (BB label, statement index) pairs
        where it is defined.
    '''

    defs: dict[variable, tuple[label, int]] = {}

    for node, data in cfg.nodes(data=True):
        bb: basic_block = data["basic_block"]
        for stmt_index, stmt in enumerate(bb.instructions):
            if isinstance(stmt, (assignment_statement, φ_statement, pop_statement)):
                defs[stmt.dest] = (node, stmt_index)

    return defs

def _mark(cfg: nx.DiGraph[label]) -> None:
    '''
    Mark live statements in the CFG.

    :param networkx.DiGraph[label] cfg: The SSA CFG.
    '''

    # Refer https://lampwww.epfl.ch/resources/lamp/teaching/advancedCompiler/2005/slides/04-SSA-6on1.pdf.

    defs = _get_defs(cfg)   # Get SSA variable def statements.
    reverse_dominance_frontiers: dict[label, set[label]] = nx.algorithms.dominance_frontiers(
        cfg.reverse(),
        next(iter(node for node, out_degree in cfg.out_degree if not out_degree))   # Start from exit node.
    )
    # print(reverse_dominance_frontiers)

    worklist: deque[tuple[label, int]] = deque()

    # Mark critical statements.
    for node, data in cfg.nodes(data=True):
        bb: basic_block = data["basic_block"]
        data["live"] = [False] * len(bb.instructions)
        for last_stmt_index, stmt in enumerate(bb.instructions):
            if isinstance(stmt, (syscall_statement, push_statement)):
                data["useful"] = data["live"][last_stmt_index] = True
                worklist.append((node, last_stmt_index))
        data["useful"] = data.get("useful", False)

    queued = set(worklist)

    while worklist:
        node, last_stmt_index = worklist.popleft()
        stmt: statement = cfg.nodes[node]["basic_block"].instructions[last_stmt_index]

        for src in src_variables(stmt):
            try:
                src_def_node, src_def_stmt_index = defs[src]
            except KeyError:
                # As globals have been initialised in the entry BB during 
                # SSA construction, this case must not occur.
                print(f"Error: variable {src} used but not defined.", file=sys.stderr)
                raise

            # if not cfg.nodes[src_def_node]["live"][src_def_stmt_index]:
            cfg.nodes[src_def_node]["useful"] = cfg.nodes[src_def_node]["live"][src_def_stmt_index] = True
            if (src_def_node, src_def_stmt_index) not in queued:
                worklist.append((src_def_node, src_def_stmt_index))
                queued.add((src_def_node, src_def_stmt_index))

        for pred in reverse_dominance_frontiers[node]:
            last_stmt_index = len(cfg.nodes[pred]["basic_block"].instructions) - 1
            cfg.nodes[pred]["useful"] = cfg.nodes[pred]["live"][last_stmt_index] = True   # Mark the branch at the end of predecessor BB.
            if (pred, last_stmt_index) not in queued:
                worklist.append((pred, last_stmt_index))
                queued.add((pred, last_stmt_index))

def _sweep(cfg: nx.DiGraph[label]) -> None:
    '''
    Sweep dead statements in the CFG.

    :param networkx.DiGraph[label] cfg: The SSA CFG.
    '''

    # Refer https://lampwww.epfl.ch/resources/lamp/teaching/advancedCompiler/2005/slides/04-SSA-6on1.pdf.

    # Exit node.
    exit_node = next(iter(node for node, out_degree in cfg.out_degree if not out_degree))
    cfg.nodes[exit_node]["useful"] = True

    # Reverse postdominator tree construction.
    reverse_postdominator_tree: dict[label, label] = nx.algorithms.immediate_dominators(
        cfg.reverse(),
        exit_node   # Start from exit node.
    )
    # print(reverse_postdominator_tree)

    for node, data in cfg.nodes(data=True):
        bb: basic_block = data["basic_block"]
        live: list[bool] = data.pop("live")
        inscount: int = 0
        for stmt_index, stmt in enumerate(bb.instructions):
            if live[stmt_index]:
                bb.instructions[inscount] = stmt
                inscount += 1
            elif isinstance(stmt, jump_statement):
                if stmt.is_conditional: # type: ignore
                    postdom = node
                    while postdom in reverse_postdominator_tree:
                        postdom = reverse_postdominator_tree[postdom]
                        if cfg.nodes[postdom]["useful"]:
                            bb.instructions[inscount] = jump_statement(postdom)
                            inscount += 1
                            data["useful"] = True
                            break
                    else:
                        pass # No postdominator is useful, so we can safely remove the conditional jump.
                else:
                    bb.instructions[inscount] = stmt
                    inscount += 1
                    data["useful"] = True
        del bb.instructions[inscount:]

    # Reconstruct the CFG.
    cfg.clear_edges()

    for node, data in cfg.nodes(data=True):
        bb: basic_block = data["basic_block"]

        last_stmt = bb.instructions[-1] if bb.instructions else None
        if isinstance(last_stmt, jump_statement):
            if last_stmt.is_conditional:
                cfg.add_edge(node, last_stmt.target1)
                cfg.add_edge(node, last_stmt.target2)
            else:
                cfg.add_edge(node, last_stmt.target)
        elif node != cfg.order() - 1:   # Not the exit node.
            cfg.add_edge(node, label(node + 1)) # Fallthrough to the next BB.

    # Remove unreachable BBs.
    reachable = set(nx.dfs_preorder_nodes(cfg, label(0)))
    unreachable = [node for node in cfg.nodes if node not in reachable]
    cfg.remove_nodes_from(unreachable)

    # Cleanup
    for node in cfg.nodes:
        del cfg.nodes[node]["useful"]

def eliminate_dead_code(cfg: nx.DiGraph[label]) -> None:
    '''
    Perform dead code elimination on the given SSA CFG.

    :param networkx.DiGraph[label] cfg: The SSA CFG to perform
        dead code elimination on.
    '''

    # Refer https://lampwww.epfl.ch/resources/lamp/teaching/advancedCompiler/2005/slides/04-SSA-6on1.pdf.

    _mark(cfg)
    _sweep(cfg)