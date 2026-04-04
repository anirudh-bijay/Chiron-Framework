from typing import Any


class operator:
    '''
    An operator in the SSA form of the program. An operator has
    a symbol representing it.

    Operators are special in that their arguments can be sourced
    from more than one register or directly from memory or can be
    constants. On the other hand, operators and syscalls expect
    their arguments to be in specific registers in a specific
    order.
    
    There need not be a one-to-one mapping between 
    operators and machine instructions.
    '''

    def __init__(self, name: str):
        '''
        Declare an operator.

        :param str name: The symbol for the operator.
        '''
        
        self._name = name

    @property
    def name(self) -> str:
        '''The symbol for this operator.'''
        return self._name
    
    def __str__(self):
        '''String representation of the operator.'''
        return self.name
    
    def __eq__(self, value: Any):
        '''Equality comparison for operators.'''
        if not isinstance(value, operator):
            return NotImplemented
        
        return self.name == value.name
    
    def __hash__(self):
        '''Hash function for operators.'''
        return hash(self.name)

# Operators for arithmetic and logical operations.

add = operator("+")
sub = operator("-")
mul = operator("*")
div = operator("/")
mod = operator("%")
pos = operator("+")
neg = operator("-")
lt  = operator("<")
gt  = operator(">")
le  = operator("<=")
ge  = operator(">=")
eq  = operator("==")
ne  = operator("!=")
bool_and = operator("and")
bool_or  = operator("or")
bool_not = operator("not")

bool_operators = [bool_and, bool_or, bool_not, lt, gt, le, ge, eq, ne]