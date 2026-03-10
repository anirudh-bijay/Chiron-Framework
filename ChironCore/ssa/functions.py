class function:
    '''
    Functions in the SSA form of the program. A function has a name.

    Unlike operators, functions are not expected to be implemented as
    single machine instructions. However, the primary distinction
    between functions and operators is that functions require their
    arguments to be placed in specific registers or in a specific order
    on the stack and place their return value similarly.
    '''

    def __init__(self, name: str):
        '''
        Declare a function.

        :param str name: The name of the function.
        '''

        self._name = name

    @property
    def name(self) -> str:
        return self._name
    
    def __str__(self):
        return self.name

