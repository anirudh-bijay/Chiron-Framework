from abc import ABC, abstractmethod

class operand(ABC):
    '''
    An operand in the SSA form of the program. This is an abstract base
    class for all operands, which can be variables, constants, or basic
    block labels.
    '''

    def __init__(self):
        pass

    @abstractmethod
    def __str__(self) -> str:
        '''String representation of the operand.'''
        pass

class variable(operand):
    '''
    A variable in the SSA form of the program. Each variable is
    uniquely identified by an index (integer). The original variable
    name is stored as a string for debugging purposes.
    '''

    def __init__(self, index: int, name: str):
        self._index = index
        self._name = name

    @property
    def index(self) -> int:
        '''The SSA version of this variable.'''
        return self._index
    
    @index.setter
    def index(self, new_index: int):
        '''Set a new index for this variable.'''
        self._index = new_index

    @property
    def name(self) -> str:
        '''The original name of this variable.'''
        return self._name

    def __str__(self):
        '''String representation of the variable.'''
        subscript_map = str.maketrans("-0123456789", "₋₀₁₂₃₄₅₆₇₈₉")
        return self.name + ('' if self.index == -1 else str(self.index).translate(subscript_map))
    
    def __eq__(self, value):
        '''Equality comparison for variables.'''
        if not isinstance(value, variable):
            return NotImplemented
        
        return self.index == value.index and self.name == value.name
    
    def __hash__(self) -> int:
        return hash((self.index, self.name))
    
class constant(operand):
    '''
    A constant in the SSA form of the program. This is an abstract base
    class for all constants, which can be of different types (e.g. int,
    bool, etc.).
    '''

    def __init__(self):
        pass

    @abstractmethod
    def __str__(self) -> str:
        '''String representation of the constant.'''
        pass

class integer_constant(constant):
    '''
    An integer constant in the SSA form of the program. This is a
    constant that represents an integer value.
    '''

    def __init__(self, value: int):
        '''
        Initialise an integer constant.

        :param int value: The integer value of the constant.
        '''
        
        super().__init__()
        self._value = value

    @property
    def value(self) -> int:
        '''The integer value of the constant.'''
        return self._value

    def __str__(self) -> str:
        return str(self.value)
    
    def __eq__(self, value):
        '''Equality comparison for integer constants.'''
        if not isinstance(value, integer_constant):
            return NotImplemented
        
        return self.value == value.value
    
class uninitialised_constant(constant):
    '''
    An uninitialised constant in the SSA form of the program.
    As ChironLang does not have scoping, it is possible for a
    variable to be used before it is defined. While the
    Python runtime would raise an error in this case, we want
    to be able to represent this situation in our SSA form.
    
    Uninitialised constants should be used only in assignment
    statements at the beginning of the program. Use the copy
    (unary +) operator.
    
    Ideally, the instruction selection phase should ignore
    such assignments.
    '''

    def __init__(self):
        super().__init__()

    def __str__(self) -> str:
        return "<undefined>"