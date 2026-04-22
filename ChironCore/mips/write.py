import networkx as nx

from ssa.label import label

def write_to_file(cfg: nx.DiGraph[label], clargs: list[str], filename: str) -> None:
    '''
    Write the given CFG to a file as a MIPS assembly program.
    The entry point is `main`, which returns 0 on completion.

    Command-line arguments and their corresponding positions
    are mentioned as a comment at the top of the file.

    :param networkx.DiGraph[label] cfg: The CFG to write to a file.
    :param list[str] clargs: The list of command-line arguments.
    :param str filename: The name of the file to write the CFG to.
    '''

    with open(filename, 'w') as f:
        if clargs:
            f.write('# Command-line arguments:\n')
            for i, arg in enumerate(clargs, start=1):
                f.write(f'#   #{i}: {arg}\n')
            f.write('\n')
        f.write('        .globl  main\n')
        f.write('main:\n')
        for node in sorted(cfg.nodes):
            f.write(f'{node}:\n')
            for instruction in cfg.nodes[node]['basic_block'].instructions:
                f.write(f'{instruction}\n')
        f.write('\n')
        f.write('        xor     $v0, $v0, $v0\n')
        f.write('        jr      $ra\n')