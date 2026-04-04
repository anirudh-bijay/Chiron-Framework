from typing import Iterable

from .statements import statement


class basic_block:
    '''
    A basic block is a sequence of instructions with exactly one entry
    point and one exit point. The entry point is the first instruction
    in the block, and the exit point is the last instruction in the
    block.

    Basic blocks are used as nodes in the control flow graph (CFG) for
    the SSA form of the program and are indexed using labels.
    The label should be unique for each basic block in the program,
    and is used as the target for jump instructions that jump to this
    block (rather than the basic block itself).
    '''

    # Constructor.
    
    def __init__(self, instructions: Iterable[statement]):
        '''
        Initialise a basic block with a sequence of instructions.

        :param int label: The unique label for this basic block.
        :param list instructions: The sequence of instructions in
            this basic block.
        '''

        self.instructions = list(instructions)
    
    # Dunder methods.

    def __str__(self):
        '''String representation of a basic block.'''
        return "\n    ".join([str(instr) for instr in self.instructions])