class label(int):
    '''
    A basic block label in the SSA form of the program. This is used
    as the destination for jumps.

    The label is an integer and uniquely identifies a basic block in
    the program.
    The actual target (in assembly) is "L" followed by the label, e.g.,
    "L0", "L1", "L2", etc.
    '''
    
    def __str__(self):
        '''String representation of a label.'''
        return f"L{int(self)}"