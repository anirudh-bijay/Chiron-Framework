from abc import ABC, abstractmethod

from .label import label
from .operands import operand, variable
from .operators import operator


class statement(ABC):
    '''
    A statement is an abstract base class for all statements in the SSA
    form of the program. Statements in the SSA form are in 3AC but are
    different from statements in the original Chiron IR:

    - For assignment statements, a destination variable is assigned
      the result of an operation on one or two source variables or
      constants. Hence, the statement must have:
        - a unary or binary operator;
        - a destination variable; and
        - one or two source variables or constants.
      
      Copies are represented as assignment statements with the unary
      ``+`` operator, e.g., ``x1 = +x0`` represents a copy of variable
      ``x0`` to ``x1``.

    - For control flow statements, the statement is a either an
      unconditional jump to a target basic block or a conditional
      jump consisting of a condition and two target basic blocks
      (one for the true case and one for the false case). The
      condition is a unary or binary logical expression on one or
      two source variables or constants.

    - For syscalls and function calls, the statement is a call
      to an assigned basic block. Arguments for the syscall are
      passed via push statements before the jump statement, and return
      values are retrieved via pop statements (see below). The
      return address is handled implicitly by the call statement.

    - Push and pop statements are used to manage the virtual stack for
      function calls and returns. A push statement pushes a variable or
      constant onto the stack, and a pop statement does the opposite.

    - φ-functions are not IR statements, but are used to merge
      variables at the join points of control flow. A φ-function has
      a destination variable and a list of source variables, one for
      each predecessor basic block.

    - No-op statements are used to earmark instructions that have been
      optimised away and should be removed in a later pass.
    '''
    
    def __init__(self):
        pass

    @abstractmethod
    def __str__(self) -> str:
        '''String representation of the statement.'''
        pass

class assignment_statement(statement):
    '''
    An assignment statement in SSA form. This is a statement of the form
    ``dest = f(src1[, src2])``, where dest is a variable, ``f`` is a unary
    or binary operator, and ``src1`` and ``src2`` are source variables or
    constants.
    '''

    def __init__(self, op: operator, dest: variable, src1: operand, src2: operand | None = None):
        '''
        Initialise an assignment statement.

        :param operator op: A unary or binary operator.
        :param variable dest: The destination variable.
        :param operand src1: The first source variable or constant.
        :param operand | None src2: The second source variable or constant (optional).
        '''

        super().__init__()
        self.dest = dest
        self.op = op
        self.src1 = src1
        self.src2 = src2

    def __str__(self):
        if self.src2 is not None:
            return f"{self.dest} = {self.src1} {self.op} {self.src2}"
        else:
            return f"{self.dest} = {self.op}{self.src1}"
        
class jump_statement(statement):
    '''
    An conditional or unconditional jump statement in SSA form.
    This is a statement of the form ``jump target``, where ``target``
    is a basic block label, or ``jump target if condition``,
    where ``condition`` is a logical expression.
    '''

    class condition:
        '''
        A condition for a conditional jump statement in SSA form.
        '''

        def __init__(self, op: operator, src1: operand, src2: operand | None = None):
            self.op = op
            self.src1 = src1
            self.src2 = src2

        def __str__(self):
            '''String representation of the condition.'''
            if self.src2 is not None:
                return f"{self.src1} {self.op} {self.src2}"
            else:
                return f"{self.op} {self.src1}"

    def __init__(self, target1: label, target2: label | None = None, cond: condition | None = None):
        '''
        Initialise a jump statement.

        :param label target1: The target basic block label for the true case
            (or the only case for an unconditional jump).
        :param label | None target2: The target basic block label for the
            false case (omitted for an unconditional jump).
        :param condition | None cond: The condition for the conditional jump
            (omitted for an unconditional jump).
        '''
        
        super().__init__()
        self._target1 = target1

        if target2 is not None and cond is None:
            raise ValueError("target2 cannot be provided without cond")
        if cond is not None and target2 is None:
            raise ValueError("cond cannot be provided without target2")
        self._target2 = target2
        self._cond = cond

    @property
    def target1(self) -> label:
        '''The target basic block label for the true case.'''
        if not self.is_conditional:
            raise ValueError("target1 cannot be accessed for an unconditional jump")
        
        return self._target1

    @property
    def target2(self) -> label:
        '''The target basic block label for the false case.'''
        if not self.is_conditional:
            raise ValueError("target2 cannot be accessed for an unconditional jump")
        
        return self._target2 # type: ignore

    @property
    def cond(self) -> condition:
        '''The condition for a conditional jump.'''
        if not self.is_conditional:
            raise ValueError("cond cannot be accessed for an unconditional jump")
        
        return self._cond # type: ignore
    
    @property
    def target(self) -> label:
        '''The target basic block label for an unconditional jump.'''
        if self.is_conditional:
            raise ValueError("target cannot be accessed for a conditional jump")
        
        return self._target1
    
    @property
    def is_conditional(self) -> bool:
        '''Whether this is a conditional jump statement.'''
        return self._cond is not None # and self._target2 is not None

    def __str__(self):
        if self.is_conditional:
            return f"jump {self.target1} if {self.cond}"
        else:
            return "jump " + str(self.target)
        
class syscall_statement(statement):
    '''
    A syscall statement in SSA form. Arguments for the syscall are
    passed via push statements before the syscall statement, and
    return values are retrieved via pop statements. The return address
    is handled implicitly by the syscall statement.
    '''

    def __init__(self):
        super().__init__()

    def __str__(self):
        return f"syscall"

# class call_statement(statement):
#     '''
#     A call statement in SSA form. This is a statement of the form
#     ``call target``, where target is a basic block label for the function
#     being called. Arguments to the function are passed via push statements
#     before the call statement, and return values are retrieved via pop
#     statements. The return address is handled implicitly by
#     the call statement.
#     '''

#     def __init__(self, target: label):
#         super().__init__()
#         self.target = target

#     def __str__(self):
#         return f"call {self.target}"
        
class push_statement(statement):
    '''
    A push statement in SSA form. This is a statement of the form
    ``push src``, where ``src`` is a variable or constant to be
    pushed onto the virtual stack for function calls.
    '''

    def __init__(self, src: operand):
        super().__init__()
        self.src = src

    def __str__(self):
        return f"push {self.src}"
    
class pop_statement(statement):
    '''
    A pop statement in SSA form. This is a statement of the form
    ``pop dest``, where ``dest`` is a variable to be popped to from
    the virtual stack for function calls.
    '''

    def __init__(self, dest: variable):
        super().__init__()
        self.dest = dest

    def __str__(self):
        return f"pop {self.dest}"
    
class φ_statement(statement):
    '''
    A φ-statement in SSA form. This is a statement of the form
    ``dest = φ(src1, src2, ...)``, where ``dest`` is a variable and ``src1``,
    ``src2``, etc. are source variables from the predecessor basic blocks.
    '''

    def __init__(self, dest: variable, srcs: list[variable], preds: list[label]):
        super().__init__()
        self.dest = dest
        self.srcs = srcs
        self.preds = preds

    def __str__(self):
        return f"{self.dest} = φ({', '.join(str(src) for src in self.srcs)})"
    
class nop_statement(statement):
    '''
    A no-op statement in SSA form. This is a statement that does nothing
    and is used to earmark instructions that have been optimised away and
    should be removed in a later pass.
    '''

    def __str__(self):
        return "nop"