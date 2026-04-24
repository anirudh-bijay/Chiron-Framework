import sys
from functools import cache

import networkx as nx
from ssa.basic_block import basic_block
from ssa.label import label
from ssa.operands import integer_constant, variable
from ssa.statements import φ_statement

from .instructions import mips_instruction
from .registers import physical_register


def _get_bb_liveness(cfg: nx.DiGraph[label])\
    -> tuple[dict[label, set[variable]], dict[label, set[variable]], dict[variable, set[label]], dict[variable, tuple[label, int]], dict[label, set[variable]], dict[label, set[variable]]]:
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

        # NOTE: Dataflow equations in the presence of φ-functions are
        # available at https://inria.hal.science/inria-00558509/document.

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

    return live_in, live_out, defsites, last_use, uevar, varkill

COLOURS = (
    tuple(physical_register(f'$t{i}') for i in range(10))  # $t0-$t9
    + tuple(physical_register(f'$s{i}') for i in range(8))  # $s0-$s7
    + tuple(physical_register(f'$a{i}') for i in range(2, 3))  # $a2
)

R = len(COLOURS)  # Number of available registers

memmap: dict[variable, int] = {}    # Maps variables to their stack offsets
next_stack_offset = 0               # Next available stack offset for spilling

def _get_bb_last_uses(cfg: nx.DiGraph[label], node: label,
                      live_in: dict[label, set[variable]], live_out: dict[label, set[variable]],
                      varkill: dict[label, set[variable]]) -> dict[variable, int]:
    '''
    Compute block-level last-uses.
    '''

    bb = cfg.nodes[node]['basic_block']
    last_uses = {}

    for stmt_index, stmt in enumerate(reversed(bb.instructions)):
        if isinstance(stmt, mips_instruction):
            for var in stmt.srcs:
                if isinstance(var, variable) and var not in last_uses and var not in live_out[bb.label]:
                    last_uses[var] = stmt_index

        # φ-functions will be considered as using their source variables in the preceding BB.
    
    # Handle arguments to φ-functions in successor BBs that are not live-out.
    for var in (live_in[bb.label] | varkill[bb.label]) - live_out[bb.label] - set(last_uses.keys()):
        last_uses[var] = len(bb.instructions)

    return last_uses

@cache
def distance_to_next_use_after(v: variable, node: label, index: int, cfg: nx.DiGraph[label]) -> int | float:
    '''
    Compute the distance to the next use of variable ``v`` after statement ``p`` in the CFG.
    The distance is measured in terms of the number of statements until the next use.
    If there are no more uses, return infinity.
    '''

    dist: int | float = float('inf')

    bb: basic_block = cfg.nodes[node]['basic_block']
    for i in range(index + 1, len(bb.instructions)):
        stmt = bb.instructions[i]
        if isinstance(stmt, mips_instruction) and v in stmt.srcs:
            dist = i - index
            return dist

    for succ in cfg.successors(node):
        if succ <= node:  # Avoid cycles
            continue
        dist = min(dist, len(bb.instructions) - index + distance_to_next_use_after(v, succ, -1, cfg))

    return dist

def evict(cfg: nx.DiGraph[label], node: label, index: int, in_regs: set[variable], in_mem: set[variable], protected: set[variable]) -> int:
    '''
    Insert stores before ``p`` to evict variables from registers
    until the number of variables in registers is at most ``R``.
    Returns the number of store instructions inserted.
    '''

    count = 0

    while len(in_regs) > R:
        v = max(in_regs - protected, key=lambda v: distance_to_next_use_after(v, node, index, cfg))
        if v not in in_mem:
            # Insert a store instruction for v before p
            if v not in memmap:
                global next_stack_offset
                memmap[v] = next_stack_offset
                next_stack_offset -= 4
                
            cfg.nodes[node]['new_instructions'][index].insert(
                0,
                mips_instruction('sw', [v, physical_register('$sp'), integer_constant(memmap[v])])
            )

            count += 1
            in_mem.add(v)
        in_regs.remove(v)

    return count

def spill_furthest_first_bb(cfg: nx.DiGraph[label], node: label, in_regs: set[variable], in_mem: set[variable],
                            live_in: dict[label, set[variable]], live_out: dict[label, set[variable]],
                            varkill: dict[label, set[variable]])\
    -> None:
    bb: basic_block = cfg.nodes[node]['basic_block']
    cfg.nodes[node]['new_instructions'] = [[] for _ in bb.instructions]

    last_uses = _get_bb_last_uses(cfg, node, live_in, live_out, varkill)

    for i, p in enumerate(bb.instructions.copy()):
        if not isinstance(p, (mips_instruction, φ_statement)):
            print(f'Warning: Unhandled statement type {type(p)} in register spilling.', file=sys.stderr)
            continue

        protected = set[variable]()
        if isinstance(p, mips_instruction):
            for v in p.srcs:    # Uses
                if isinstance(v, variable) and v not in in_regs:
                    # TODO: Insert a load instruction for v before p
                    if v not in memmap:
                        print(f'Warning: Variable {v} loaded before being spilled.', file=sys.stderr)
                        global next_stack_offset
                        memmap[v] = next_stack_offset
                        next_stack_offset -= 4

                    cfg.nodes[node]['new_instructions'][i].append(
                        mips_instruction('lw', [v, physical_register('$sp'), integer_constant(memmap[v])])
                    )

                    in_regs.add(v)
                    protected.add(v)
            evict(cfg, node, i, in_regs, in_mem, protected)

        for v in p.srcs:        # Uses
            if isinstance(v, variable) and v in last_uses and last_uses[v] == i:
                in_regs.remove(v)

        protected.clear()
        v = p.dest              # Defs
        if isinstance(v, variable):
            in_regs.add(v)
            protected.add(v)
        evict(cfg, node, i, in_regs, in_mem, protected)

    # Remove variables that are args to φ-functions in successor BBs
    # if they are not live-out.
    in_regs -= last_uses.keys()

def _get_maxlive(cfg: nx.DiGraph[label], node: label,
                 live_in: dict[label, set[variable]], live_out: dict[label, set[variable]],
                 varkill: dict[label, set[variable]]) -> int:
    '''
    Compute the maximum number of simultaneously live variables in the given BB.
    '''

    bb = cfg.nodes[node]['basic_block']
    live = live_in[bb.label].copy()
    maxlive = len(live)
    last_uses = _get_bb_last_uses(cfg, node, live_in, live_out, varkill)

    for i, stmt in enumerate(bb.instructions):
        if isinstance(stmt, mips_instruction):
            for var in stmt.srcs:
                if isinstance(var, variable) and var in last_uses and last_uses[var] == i:
                    live.remove(var)

        if isinstance(stmt.dest, variable):
            live.add(stmt.dest)

        maxlive = max(maxlive, len(live))

    return maxlive

def compute_in_regs(cfg: nx.DiGraph[label], node: label, in_regs: dict[label, set[variable]],
                    live_in: dict[label, set[variable]], live_out: dict[label, set[variable]],
                    varkill: dict[label, set[variable]]) -> None:
    '''
    Compute the set of variables that need to be in registers at the entry of the given BB.
    '''

    bb = cfg.nodes[node]['basic_block']
    
    for stmt in bb.instructions:
        if isinstance(stmt, φ_statement) and max(stmt.preds) >= node:
            loop = True
            break
    else:
        loop = False

    if not loop:
        allpreds_in_regs = set.intersection(*(in_regs[pred] for pred in cfg.predecessors(node)))
        somepreds_in_regs = sorted(set.union(*(in_regs[pred] for pred in cfg.predecessors(node))) - allpreds_in_regs,
                                   key=lambda v: distance_to_next_use_after(v, node, -1, cfg),
                                   reverse=True)
        in_regs[node] = allpreds_in_regs

        i = 0
        while len(in_regs[node]) < R and len(somepreds_in_regs) - i > 0:
            v = somepreds_in_regs[i]
            in_regs[node].add(v)
            i += 1
    else:
        maxlive = _get_maxlive(cfg, node, live_in, live_out, varkill)
        in_regs[node] = set()
        live_in_copy = sorted(live_in[node] - in_regs[node],
                              key=lambda v: distance_to_next_use_after(v, node, -1, cfg),
                              reverse=False)
        
        i = 0
        while (
            len(in_regs[node]) < R
            and len(live_in_copy) - i > len(in_regs[node])
            and len(in_regs[node]) < R + (len(live_in_copy) - i) - maxlive
        ):
            v = live_in_copy[i]
            in_regs[node].add(v)
            i += 1

def spill_furthest_first(cfg: nx.DiGraph[label], live_in: dict[label, set[variable]], live_out: dict[label, set[variable]],
                         varkill: dict[label, set[variable]]) -> None:
    '''
    Perform furthest-first spilling on the given CFG.
    '''

    in_regs: dict[label, set[variable]] = {}

    # Produce toposort of the CFG, ignoring loop backedges.
    for node in nx.topological_sort(nx.DiGraph((x, y) for x, y in cfg.edges if x < y)):
        compute_in_regs(cfg, node, in_regs, live_in, live_out, varkill)
        spill_furthest_first_bb(cfg, node, in_regs[node], set[variable](), live_in, live_out, varkill)

    for node in cfg.nodes:
        bb = cfg.nodes[node]['basic_block']
        new_instructions = cfg.nodes[node]['new_instructions']
        i = 0
        while i < len(bb.instructions):
            bb.instructions[i:i] = new_instructions[i]
            i += len(new_instructions[i]) + 1

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
                try:
                    colour_assignment[stmt.dest] = next(colour for colour in COLOURS if colour not in assigned_colours)
                except StopIteration:
                    if stmt.dest not in memmap:
                        global next_stack_offset
                        memmap[stmt.dest] = next_stack_offset
                        next_stack_offset -= 4
                    colour_assignment[stmt.dest] = memmap[stmt.dest]
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

    live_in, live_out, defsites, last_use, uevar, varkill = _get_bb_liveness(cfg)
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
            inst_list.append(mips_instruction('move', [physical_register('$at'), cycle[0]]))
            for i in range(len(cycle) - 1):
                dest = cycle[i]
                src = cycle[i + 1]
                inst_list.append(mips_instruction('move', [dest, src]))
            inst_list.append(mips_instruction('move', [cycle[-1], physical_register('$at')]))

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
            inst_list.append(mips_instruction('move', [physical_register('$at'), cycle[0]]))
            for i in range(len(cycle) - 1):
                dest = cycle[i]
                src = cycle[i + 1]
                inst_list.append(mips_instruction('move', [dest, src]))
            inst_list.append(mips_instruction('move', [cycle[-1], physical_register('$at')]))

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

    for node, data in cfg.nodes(data=True):
        bb: basic_block = data["basic_block"]
        for stmt in bb.instructions:
            if isinstance(stmt, mips_instruction):
                for i, var in enumerate(stmt.operands):
                    if isinstance(var, variable):
                        stmt.operands[i] = colour_assignment[var]

    for node, data in cfg.nodes(data=True):
        bb: basic_block = data["basic_block"]

        i = 0
        while i < len(bb.instructions):
            stmt = bb.instructions[i]
            if not isinstance(stmt, mips_instruction):
                print(f'Warning: Unhandled statement type {type(stmt)} in register spilling.', file=sys.stderr)
                i += 1
                continue

            pre_insts: list[mips_instruction] = []
            post_insts: list[mips_instruction] = []
            count = 0
            for j, var in enumerate(stmt.operands):
                if isinstance(var, int) and not isinstance(var, label):
                    if var in stmt.srcs:
                        if count == 0:
                            pre_insts.append(mips_instruction('lw', [physical_register('$a3'), physical_register('$sp'), integer_constant(var)]))
                            count += 1
                            stmt.operands[j] = physical_register('$a3')
                        elif count == 1:
                            pre_insts.append(mips_instruction('lw', [physical_register('$v1'), physical_register('$sp'), integer_constant(var)]))
                            count += 1
                            stmt.operands[j] = physical_register('$v1')
                        else:
                            print(f'Error: Non-3AC instruction {stmt} in BB {node}', file=sys.stderr)
                    elif var == stmt.dest:
                        post_insts.append(mips_instruction('sw', [physical_register('$a3'), physical_register('$sp'), integer_constant(var)]))
                        stmt.operands[j] = physical_register('$a3')
            bb.instructions[i:i] = pre_insts
            i += len(pre_insts) + 1
            bb.instructions[i:i] = post_insts
            i += len(post_insts)

        while i < len(bb.instructions) - 1:
            stmt: mips_instruction = bb.instructions[i]
            next_stmt: mips_instruction = bb.instructions[i + 1]
            if stmt.name == 'sw' and next_stmt.name == 'lw' and stmt.operands == next_stmt.operands:
                # Remove redundant store-load pair.
                bb.instructions.pop(i + 1)
                bb.instructions.pop(i)
            else:
                i += 1