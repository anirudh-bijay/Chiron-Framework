import sys

import networkx as nx
from ssa.basic_block import basic_block
from ssa.label import label
from ssa.operands import variable
from ssa.statements import φ_statement

from .instructions import mips_instruction
from .registers import physical_register


def _get_liveness(cfg: nx.DiGraph[label])\
    -> tuple[dict[label, set[variable]], dict[label, set[variable]], dict[variable, set[label]], dict[variable, tuple[label, int]]]:
    '''
    Get the live-in and live-out sets for each basic block
    in the control flow graph.
    '''

    live_in: dict[label, set[variable]] = {bb: set() for bb in cfg.nodes}
    live_out: dict[label, set[variable]] = {bb: set() for bb in cfg.nodes}

    # This stuff is very similar to that in ../ssa/varinfo.py.
    # Refer https://sites.cs.ucsb.edu/~yufeiding/cs293s/slides/293s_04_GCSE_DFA.pdf;
    # the terminology used here is the same.
    uevar: dict[label, set[variable]] = {bb: set() for bb in cfg.nodes} # Upward-exposed variables in each BB.
    varkill: dict[label, set[variable]] = {bb: set() for bb in cfg.nodes} # Variables defined in each BB.

    defsites: dict[variable, set[label]] = {}
    last_use: dict[variable, tuple[label, int]] = {}
    
    for node, data in cfg.nodes(data=True):
        bb: basic_block = data["basic_block"]
        for stmt_index, stmt in enumerate(bb.instructions):
            if not isinstance(stmt, (mips_instruction, φ_statement)):
                print(f'Warning: Unhandled statement type {type(stmt)} in liveness analysis.', file=sys.stderr)
                continue

            if isinstance(stmt, mips_instruction):
                for var in stmt.srcs:
                    # Add to uevar if not already defined.
                    if isinstance(var, variable) and var not in varkill[node]:
                        uevar[node].add(var)
                    # Update last use.
                    if isinstance(var, variable):
                        last_use[var] = max(last_use.get(var, (node, -1)), (node, stmt_index))

            # NOTE: The arguments of a φ-function are used by the
            # preceding BB, not by the BB containing the φ-function.
            
            # The result of a φ-function is considered defined in the BB
            # containing the φ-function, not in the preceding BBs. Why?
            # Although the moves that create the result are placed in the
            # preceding BBs, we want to use the same register for the result,
            # so we want to consider it centrally.
            if isinstance(dest := stmt.dest, variable):
                varkill[node].add(dest)
                if dest not in defsites:
                    defsites[dest] = set()
                defsites[dest].add(node)

        # Now, we need to handle the variables in the φ-functions of successors
        # of this BB.
        for succ in cfg.successors(node):
            succ_bb: basic_block = cfg.nodes[succ]["basic_block"]
            for stmt in succ_bb.instructions:
                if isinstance(stmt, φ_statement):
                    for pred, var in zip(stmt.preds, stmt.srcs):
                        if pred == node and isinstance(var, variable):
                            # Add to uevar if not already defined.
                            if var not in varkill[pred]:
                                uevar[pred].add(var)
                            # Update last use.
                            last_use[var] = max(last_use.get(var, (pred, -1)), (pred, pred_index := len(cfg.nodes[pred]["basic_block"].instructions) - 1))

    # Iterate until convergence.
    # Slide 31: Iterate over nodes rather than maintaining a worklist.
    # Slides 37-38: Iterate over nodes in postorder.
    postorder = list(nx.dfs_postorder_nodes(cfg, source=label(0)))
    flag = True
    while flag:
        flag = False

        for node in postorder:  # Slide 31: Iteration is done over nodes rather than a worklist.
            # Slide 27: liveout is the union of livein of successors.
            new_live_out = set()
            for succ in cfg.successors(node):
                new_live_out |= live_in[succ]

            # # Also add the variables in the φ-functions of successors
            # # that come from this BB.
            # for succ in cfg.successors(node):
            #     succ_bb: basic_block = cfg.nodes[succ]["basic_block"]
            #     for stmt in succ_bb.instructions:
            #         if isinstance(stmt, φ_statement):
            #             for var, src_bb in zip(stmt.srcs, stmt.preds):
            #                 if src_bb == node and isinstance(var, variable):
            #                     new_live_out.add(var)

            live_out[node] = new_live_out

            # Slide 25: livein[B] = (liveout[B] - varkill[B]) ∪ uevar[B].
            new_live_in = (live_out[node] - varkill[node]) | uevar[node]

            if new_live_in != live_in[node]:
                live_in[node] = new_live_in
                flag = True

    return live_in, live_out, defsites, last_use#, uevar, varkill

def _get_dfs_backedges(cfg: nx.DiGraph[label]) -> dict[label, set[label]]:
    '''
    Get the backedges in the CFG with respect to a DFS traversal.
    '''

    entered_subtree: set[label] = set()
    exited_subtree: set[label] = set()
    backedges: dict[label, set[label]] = {}

    for u, v, status in nx.dfs_labeled_edges(cfg, source=label(0)):
        if status == 'forward':
            entered_subtree.add(v)
        elif status == 'reverse':
            exited_subtree.add(u)
        elif status == 'nontree':
            if v in entered_subtree and v not in exited_subtree:
                if u not in backedges:
                    backedges[u] = set()
                backedges[u].add(v)

    return backedges

COLOURS = (
    tuple(physical_register(f'$t{i}') for i in range(10))  # $t0-$t9
    + tuple(physical_register(f'$s{i}') for i in range(8))  # $s0-$s7
)

EXPANDED_COLOURS = (
    tuple(physical_register(f'$a{i}') for i in range(4))  # $a0-$a3
    + COLOURS
)

def _colour_recursive(
    cfg: nx.DiGraph[label],
    node: label,
    live_in: dict[label, set[variable]],
    live_out: dict[label, set[variable]],
    defsites: dict[variable, set[label]],
    last_use: dict[variable, tuple[label, int]],
    dominator_tree: dict[label, list[label]],
    colour_assignment: dict[variable, physical_register]
) -> None:
    '''
    Colour the interference graph for the given basic block
    without actually constructing it, then recurse on its
    successors in the dominator tree. The colours are mapped
    to the variables in the basic block.
    '''

    assigned_colours = {colour_assignment[var] for var in live_in[node]}

    bb = cfg.nodes[node]["basic_block"]
    for stmt_index, stmt in enumerate(bb.instructions):
        if not isinstance(stmt, (mips_instruction, φ_statement)):
            print(f'Warning: Unhandled statement type {type(stmt)} in interference graph colouring.', file=sys.stderr)
            continue

        for var in stmt.srcs:
            if isinstance(var, variable) and last_use[var] == (node, stmt_index):
                # This is the last use of var, so we can free its register after this instruction.
                assigned_colours.remove(colour_assignment[var])

        if isinstance(stmt.dest, variable):
            if stmt.dest not in colour_assignment:
                # WRONG:
                # if stmt.dest not in live_out[node]:
                #     # This variable is not live after this instruction, so we can assign it any colour.
                #     colour_assignment[stmt.dest] = next(colour for colour in EXPANDED_COLOURS if colour not in assigned_colours)
                # else:
                    colour_assignment[stmt.dest] = next(colour for colour in COLOURS if colour not in assigned_colours)
            assigned_colours.add(colour_assignment[stmt.dest])

    # Recurse.
    for child in dominator_tree[node]:
        _colour_recursive(cfg, child, live_in, live_out, defsites, last_use, dominator_tree, colour_assignment)

def colour_cfg(cfg: nx.DiGraph[label], print_debug: bool = False) -> dict[variable, physical_register]:
    '''
    Colour the interference graph for the given CFG without
    actually constructing it. The colours are mapped to the
    variables in the SSA CFG.

    :param networkx.DiGraph[label] cfg: The SSA CFG whose
        interference graph to colour.
    '''

    live_in, live_out, defsites, last_use = _get_liveness(cfg)
    dominator_tree: dict[label, list[label]] = {node: [] for node in cfg.nodes}
    for child, parent in nx.algorithms.immediate_dominators(cfg, label(0)).items():
        dominator_tree[parent].append(child)

    colour_assignment: dict[variable, physical_register] = {}

    # Precolour constrained locals.
    for node, data in cfg.nodes(data=True):
        bb: basic_block = data["basic_block"]
        for stmt in bb.instructions:
            if (
                isinstance(stmt, mips_instruction) and stmt.name == 'move'
                and isinstance(stmt.operands[0], physical_register) and isinstance(stmt.operands[1], variable)
                and stmt.operands[1] not in live_in[node] and stmt.operands[1] not in live_out[node] # Local to BB
            ):
                colour_assignment[stmt.operands[1]] = stmt.operands[0]

    _colour_recursive(cfg, label(0), live_in, live_out, defsites, last_use, dominator_tree, colour_assignment)

    if print_debug:
        for node, data in cfg.nodes(data=True):
            bb: basic_block = data["basic_block"]
            for stmt in bb.instructions:
                if isinstance(stmt, mips_instruction):
                    for i, var in enumerate(stmt.operands):
                        if isinstance(var, variable):
                            stmt.operands[i] = colour_assignment[var]

    return colour_assignment

def _remove_self_copies(cfg: nx.DiGraph[label]) -> None:
    '''
    Remove self-copy instructions from the CFG (of the form `move $reg, $reg`).
    '''

    for node, data in cfg.nodes(data=True):
        bb: basic_block = data["basic_block"]
        bb.instructions = [stmt for stmt in bb.instructions if not (isinstance(stmt, mips_instruction) and stmt.name == 'move' and len(stmt.operands) == 2 and stmt.operands[0] == stmt.operands[1])]

def out_of_ssa(cfg: nx.DiGraph[label], colour_assignment: dict[variable, physical_register]) -> None:
    '''
    Perform out-of-SSA transformation on the given CFG by
    replacing φ-statements with copy instructions. This is
    done in-place.

    :param networkx.DiGraph[label] cfg: The SSA CFG to transform.

    :param dict[variable, physical_register] colour_assignment:
        The mapping from variables to physical registers obtained
        from register allocation.

    '''

    beginning_perms: dict[label, nx.DiGraph[physical_register]] = {node: nx.DiGraph() for node in cfg.nodes}
    ending_perms: dict[label, nx.DiGraph[physical_register]] = {node: nx.DiGraph() for node in cfg.nodes}

    for u, v in cfg.edges:
        bb_u: basic_block = cfg.nodes[u]["basic_block"]
        bb_v: basic_block = cfg.nodes[v]["basic_block"]

        if cfg.in_degree(v) == 1:
            for stmt in bb_v.instructions:
                if isinstance(stmt, φ_statement):
                    for pred, src in zip(stmt.preds, stmt.srcs):
                        if pred == u:
                            beginning_perms[v].add_edge(colour_assignment[stmt.dest], colour_assignment[src])
                            break
        elif cfg.out_degree(u) == 1:
            for stmt in bb_v.instructions:
                if isinstance(stmt, φ_statement):
                    for pred, src in zip(stmt.preds, stmt.srcs):
                        if pred == u:
                            ending_perms[u].add_edge(colour_assignment[stmt.dest], colour_assignment[src])
                            break
        else:
            print(f'Error: Critical edge detected from {u} to {v} during out-of-SSA transformation.', file=sys.stderr)

    for node, data in cfg.nodes(data=True):
        bb: basic_block = data["basic_block"]

        # Stage 1: Prepend copies.
        inst_list: list[mips_instruction] = []

        # Deal with cycles first.
        for cycle in tuple(nx.simple_cycles(beginning_perms[node])):
            inst_list.append(mips_instruction('move', [physical_register('$v1'), cycle[0]]))
            for i in range(len(cycle) - 1):
                dest = cycle[i]
                src = cycle[i + 1]
                inst_list.append(mips_instruction('move', [dest, src]))
            inst_list.append(mips_instruction('move', [cycle[-1], physical_register('$v1')]))

            beginning_perms[node].remove_nodes_from(cycle)

        # Now deal with chains.
        for wcc in nx.weakly_connected_components(beginning_perms[node]):
            chain: tuple[physical_register] = tuple(nx.topological_sort(beginning_perms[node].subgraph(wcc))) # type: ignore
            for i in range(len(chain) - 1):
                dest = chain[i]
                src = chain[i + 1]
                inst_list.append(mips_instruction('move', [dest, src]))
            
        # Remove φ-statements.
        bb.instructions = [stmt for stmt in bb.instructions if not isinstance(stmt, φ_statement)]

        # Prepend the copy instructions.
        bb.instructions = inst_list + bb.instructions

        # Stage 2: Append copies.
        inst_list = []

        # Deal with cycles first.
        for cycle in tuple(nx.simple_cycles(ending_perms[node])):
            inst_list.append(mips_instruction('move', [physical_register('$v1'), cycle[0]]))
            for i in range(len(cycle) - 1):
                dest = cycle[i]
                src = cycle[i + 1]
                inst_list.append(mips_instruction('move', [dest, src]))
            inst_list.append(mips_instruction('move', [cycle[-1], physical_register('$v1')]))

            ending_perms[node].remove_nodes_from(cycle)

        # Now deal with chains.
        for wcc in nx.weakly_connected_components(ending_perms[node]):
            chain: tuple[physical_register] = tuple(nx.topological_sort(ending_perms[node].subgraph(wcc))) # type: ignore
            for i in range(len(chain) - 1):
                dest = chain[i]
                src = chain[i + 1]
                inst_list.append(mips_instruction('move', [dest, src]))

        # Append the copy instructions.
        jump = bb.instructions.pop() if bb.instructions and bb.instructions[-1].name.startswith(('j', 'b')) else None # type: ignore
        bb.instructions.extend(inst_list)
        if jump:
            bb.instructions.append(jump)

    _remove_self_copies(cfg)