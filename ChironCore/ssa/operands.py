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
        '''The unique index of this variable.'''
        return self._index

    @property
    def name(self) -> str:
        '''The original name of this variable.'''
        return self._name

    def __str__(self):
        '''String representation of the variable.'''
        subscript_map = str.maketrans("-0123456789", "₋₀₁₂₃₄₅₆₇₈₉")
        return self.name + str(self.index).translate(subscript_map)
    
    def __eq__(self, value):
        '''Equality comparison for variables.'''
        if not isinstance(value, variable):
            return NotImplemented
        
        return self.index == value.index and self.name == value.name
    
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