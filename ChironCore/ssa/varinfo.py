import networkx as nx

from .basic_block import basic_block
from .label import label
from .operands import variable
from .renumber import src_variables
from .statements import assignment_statement, pop_statement


def get_varinfo(cfg: nx.DiGraph[label]) -> dict[str, dict[variable, set[label]] | set[variable]]:
    '''
    Get information pertaining to variables in the 3AC CFG for
    use in SSA generation.

    :param networkx.DiGraph[label] cfg: The 3AC CFG.
    :return dict[variable, set[label]]: *defsites:*
        A dictionary mapping each variable
        to the set of basic blocks where it is defined.
    :return set[variable]: *globals:*
        The set of global variables (variables
        that are used before definition in any BB).
        
    The above are returned in a dictionary.
    '''

    # See https://sites.cs.ucsb.edu/~yufeiding/cs293s/slides/293s_04_GCSE_DFA.pdf
    # for upward-exposed variables,
    # https://sites.cs.ucsb.edu/~yufeiding/cs293s/slides/293S_07_SSA_dead.pdf
    # for upward-exposed variables and globals, and
    # https://www.cs.toronto.edu/%7Epekhimenko/courses/cscd70-w20/docs/Lecture%204%20%5BSSA%5D%2002.03.2020.pdf.
    # for defsites.
    defsites: dict[variable, set[label]] = {}
    globals: set[variable] = set()

    # Complexity linear in the number of 3AC statements.
    for node, data in cfg.nodes(data=True):
        bb: basic_block = data["basic_block"]
        for stmt in bb.instructions:
            # Add to globals if not already defined.
            for var in src_variables(stmt):
                if node not in defsites.get(var, set()):
                    globals.add(var)

            # Add to defsites.
            if isinstance(stmt, (assignment_statement, pop_statement)):
                if stmt.dest not in defsites:
                    defsites[stmt.dest] = set()
                defsites[stmt.dest].add(node)

    return {
        "defsites": defsites,
        "globals": globals
    }