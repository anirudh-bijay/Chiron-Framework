# Split critical edges.

import networkx as nx

from ssa.statements import jump_statement
from ssa.label import label
from ssa.basic_block import basic_block

def split_critical_edges(cfg: nx.DiGraph[label]) -> None:
    '''
    Split critical edges in the given CFG in-place.

    :param networkx.DiGraph[label] cfg: The CFG to split critical edges in.
    '''

    # First, we find all critical edges.
    critical_edges = [(u, v) for u, v in cfg.edges if cfg.out_degree(u) > 1 and cfg.in_degree(v) > 1]

    if not critical_edges:
        return
    
    # We save the exit node.
    exit_node = label(max(cfg.nodes))

    # Now we split each critical edge.
    for u, v in critical_edges:
        new_node = label(max(cfg.nodes) + 1)
        new_basic_block = basic_block([jump_statement(v)])
        if not isinstance(cfg.nodes[u]["basic_block"].instructions[-1], jump_statement):
            raise TypeError(f'Expected the last statement of basic block {u} to be a jump statement, but got {cfg.nodes[u]["basic_block"].instructions[-1]}.')
        
        old_jump: jump_statement = cfg.nodes[u]["basic_block"].instructions[-1]
        if old_jump.target1 == v:
            new_jump = jump_statement(new_node, old_jump.target2, old_jump.cond)
        elif old_jump.target2 == v:
            new_jump = jump_statement(old_jump.target1, new_node, old_jump.cond)
        else:
            raise ValueError(f'Expected the last statement of basic block {u} to have control flow to {v}, but got {cfg.nodes[u]["basic_block"].instructions[-1]}.')
        cfg.nodes[u]["basic_block"].instructions[-1] = new_jump

        cfg.add_node(new_node, basic_block=new_basic_block)
        cfg.add_edge(u, new_node)
        cfg.add_edge(new_node, v)
        cfg.remove_edge(u, v)

    # Finally, we create a new exit node.
    new_exit_node = label(max(cfg.nodes) + 1)
    new_exit_basic_block = basic_block([])
    cfg.nodes[exit_node]["basic_block"].instructions.append(jump_statement(new_exit_node))
    cfg.add_node(new_exit_node, basic_block=new_exit_basic_block)