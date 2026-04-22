import sys
from collections import deque

import networkx as nx

from .basic_block import basic_block
from .dce import eliminate_dead_code
from .label import label
from .operands import uninitialised_constant, variable
from .operators import operator
from .renumber import src_variables
from .statements import (assignment_statement, jump_statement, pop_statement,
                         push_statement, statement, φ_statement)
from .varinfo import get_varinfo


def _get_defsites(cfg: nx.DiGraph[label]) -> dict[variable, set[label]]:
    '''
    Get the BBs where each variable is defined (assigned to).

    :param networkx.DiGraph[label] cfg: The 3AC CFG.
    :return dict[variable, set[label]]: A dictionary mapping each variable
        to the set of basic blocks where it is defined.
    '''

    defsites: dict[variable, set[label]] = {}

    # Complexity linear in the number of 3AC statements.
    for node, data in cfg.nodes(data=True):
        bb: basic_block = data["basic_block"]
        for stmt in bb.instructions:
            if isinstance(stmt, assignment_statement):
                if stmt.dest not in defsites:
                    defsites[stmt.dest] = set()
                defsites[stmt.dest].add(node)

    return defsites

def _initialise_globals(cfg: nx.DiGraph[label], globals: set[variable], defsites: dict[variable, set[label]]) -> None:
    '''
    Assign the special constant <undefined> to global variables (variables
    that are used before being defined in any BB) in the CFG.

    :param networkx.DiGraph[label] cfg: The 3AC CFG.
    :param set[variable] globals: The set of global variables.
    :param dict[variable, set[label]] defsites:
        A dictionary mapping each variable to the set of basic blocks
        where it is defined.
    '''

    start_bb: basic_block = cfg.nodes[label(0)]["basic_block"]
    start_bb.instructions = [assignment_statement(operator('+'), variable(var.index, var.name), uninitialised_constant()) for var in globals] + start_bb.instructions
    for var in globals:
        if var not in defsites:
            # Reference to uninitialised variable that is not defined anywhere in the program.
            defsites[var] = set()
        defsites[var].add(label(0))

def _rename_uses(stmt: statement, stacks: dict[str, list[int]]) -> None:
    '''
    Rename the variables used (not defined) in the given statement
    with the top indices from the stacks corresponding to the variables.
    φ-statements are not handled by this routine.

    :param statement stmt: A 3AC statement.
    :param dict[str, list[int]] stacks: The current stacks for each
        variable name.
    '''

    match stmt:
        case assignment_statement():
            if isinstance(stmt.src1, variable):
                stmt.src1.index = stacks[stmt.src1.name][-1]
            if isinstance(stmt.src2, variable):
                stmt.src2.index = stacks[stmt.src2.name][-1]

        case jump_statement():
            if stmt.is_conditional:
                if isinstance(stmt.cond.src1, variable):
                    stmt.cond.src1.index = stacks[stmt.cond.src1.name][-1]
                if isinstance(stmt.cond.src2, variable):
                    stmt.cond.src2.index = stacks[stmt.cond.src2.name][-1]

        case push_statement():
            if isinstance(stmt.src, variable):
                stmt.src.index = stacks[stmt.src.name][-1]

def _walk_dominator_tree(
    dominator_tree: dict[label, list[label]],
    node: label,
    cfg: nx.DiGraph[label],
    stacks: dict[str, list[int]],
    indices: dict[str, int],
    phi_targets: dict[label, set[variable]]
) -> None:
    '''
    Walk the dominator tree of the CFG to rename variables in SSA form.
    '''

    original_stack_lengths: dict[str, int] = {var: len(stack) for var, stack in stacks.items()}
    bb: basic_block = cfg.nodes[node]["basic_block"]

    for stmt in bb.instructions:
        # Handle uses.
        _rename_uses(stmt, stacks)

        # Handle defs.
        if isinstance(stmt, (assignment_statement, φ_statement, pop_statement)):
            if stmt.dest.name not in stacks:
                stacks[stmt.dest.name] = []

            stacks[stmt.dest.name].append(indices.get(stmt.dest.name, 0))
            indices[stmt.dest.name] = indices.get(stmt.dest.name, 0) + 1
            stmt.dest.index = stacks[stmt.dest.name][-1]

    for child in dominator_tree[node]:
        _walk_dominator_tree(dominator_tree, child, cfg, stacks, indices, phi_targets)

    # See https://www.cse.iitm.ac.in/~rupesh/teaching/pa/jan17/scribes/0-ssa.pdf
    # for details on renaming variables used (not defined) in φ-statements.
    for child in cfg.successors(node):
        if child in phi_targets:
            for var in phi_targets[child]:
                if var.name not in stacks or len(stacks[var.name]) == 0:
                    # This is an error, since we are anyways initialising all globals. 
                    print(f"Error: Variable {var.name} used in φ-statement in BB {child} has no definition from {node}.", file=sys.stderr)
                    continue

                # Update the φ-statement for ``var`` in ``child`` with the current version of ``var``.
                for stmt in cfg.nodes[child]["basic_block"].instructions:
                    if isinstance(stmt, φ_statement) and stmt.dest.name == var.name:
                        stmt.srcs.append(variable(stacks[var.name][-1], var.name))
                        stmt.preds.append(node)
                        break

    for var in stacks:
       del stacks[var][original_stack_lengths.get(var, 0):]

def ssa_cfg_from_tac_cfg(cfg: nx.DiGraph[label], dce=True, print_debug: bool = False) -> None:
    '''
    Convert the 3AC CFG constructed from the IR to an SSA CFG in place
    by inserting φ-statements where necessary. A semi-pruned minimal SSA form
    is constructed.

    :param networkx.DiGraph[label] cfg: The control flow graph to convert to SSA form.
    :param bool dce: Whether to perform dead code elimination for SSA pruning.
    :param bool print_debug: Whether to print the SSA form.

    :note: See https://doi.org/10.1145/115372.115320 for details on the algorithm.
    '''

    # Refer https://www.cs.toronto.edu/%7Epekhimenko/courses/cscd70-w20/docs/Lecture%204%20%5BSSA%5D%2002.03.2020.pdf.
    # Page 31-32: Using dominance frontiers to place φ-functions.
    dominance_frontiers: dict[label, set[label]] = nx.algorithms.dominance_frontiers(cfg, label(0))
    varinfo = get_varinfo(cfg)
    _initialise_globals(cfg, varinfo["globals"], varinfo["defsites"]) # type: ignore

    phi_targets: dict[label, set[variable]] = {}
    phi_nodes: dict[variable, set[label]] = {}

    for var, var_defsites in {
        var: sites for var, sites in varinfo["defsites"].items() # type: ignore
        if var in varinfo["globals"]
    }.items():
        worklist = deque(var_defsites)
        queued = set(var_defsites)  # Has a node already been added to the worklist?

        while worklist:
            defsite = worklist.popleft()
            
            for node in dominance_frontiers[defsite]:
                if node not in phi_targets:
                    phi_targets[node] = set()

                if var in phi_targets[node]:
                    continue  # φ-statement for ``var`` already exists in ``node``.

                # Insert φ-statement for ``var`` at the start of ``node``.
                phi_targets[node].add(var)
                cfg.nodes[node]["basic_block"].instructions.insert(0, φ_statement(variable(var.index, var.name), [], []))
                # CAUTION: Here, we use φ_statement(variable(var.index, var.name), [], []) instead
                # of φ_statement(var, [], []) to create a deep copy. This change is made from
                # observation.
                
                # ``var`` now has a φ-statement in ``node``.
                if var not in phi_nodes:
                    phi_nodes[var] = set()
                phi_nodes[var].add(node)

                if node not in queued:
                    worklist.append(node)
                    queued.add(node)

    # Page 33: Renaming variables.
    stacks: dict[str, list[int]] = {}
    indices: dict[str, int] = {}

    # Dominator tree construction.
    dominator_tree: dict[label, list[label]] = {node: [] for node in cfg.nodes}
    for child, parent in nx.algorithms.immediate_dominators(cfg, label(0)).items():
        dominator_tree[parent].append(child)

    # Dominator tree walk.
    _walk_dominator_tree(dominator_tree, label(0), cfg, stacks, indices, phi_targets)

    # Remove duplicate source variables in φ-statements.
    for node in cfg.nodes:
        bb: basic_block = cfg.nodes[node]["basic_block"]
        for stmt in bb.instructions:
            if isinstance(stmt, φ_statement):
                temp = list(set(zip(stmt.srcs, stmt.preds)))
                stmt.srcs = [t[0] for t in temp]
                stmt.preds = [t[1] for t in temp]

    # Perform dead code elimination to remove any φ-statements that are not useful.
    if dce:
        eliminate_dead_code(cfg)

    # Print SSA statements for debugging.
    if print_debug:
        for i in range(len(cfg.nodes)):
            bb = cfg.nodes[label(i)]["basic_block"]
            print(f"L{i}:")
            print("    \n".join(f"  {stmt}" for stmt in bb.instructions))