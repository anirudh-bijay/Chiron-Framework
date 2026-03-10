from typing import Any, Generator

from .label import label
from .operands import operand, variable, integer_constant
from .operators import operator
from .statements import statement, assignment_statement, jump_statement, syscall_statement, push_statement, nop_statement
from ChironAST import ChironAST

############### PLACEHOLDER IMPLEMENTATIONS ###############
def syscall_num(instr: ChironAST.MoveCommand | ChironAST.PenCommand | ChironAST.GotoCommand) -> integer_constant:
    if isinstance(instr, ChironAST.MoveCommand):
        match instr.direction:
            case "forward":
                return integer_constant(33)
            case "backward":
                return integer_constant(34)
            case "left":
                return integer_constant(35)
            case "right":
                return integer_constant(36)
            case _:
                raise ValueError("Unsupported move command for syscall number conversion.")
            
    if isinstance(instr, ChironAST.PenCommand):
        match instr.status:
            case "penup":
                return integer_constant(38)
            case "pendown":
                return integer_constant(39)
            case _:
                raise ValueError("Unsupported pen command for syscall number conversion.")
            
    if isinstance(instr, ChironAST.GotoCommand):
        return integer_constant(37)
    
    raise TypeError("Unsupported instruction type for syscall number conversion.")
############################################################

def _to_operand(expr: ChironAST.Value | ChironAST.BoolFalse | ChironAST.BoolTrue) -> operand:
    if isinstance(expr, ChironAST.Var):
        return variable(-1, expr.varname)
    elif isinstance(expr, ChironAST.Num):
        return integer_constant(expr.val)
    elif isinstance(expr, ChironAST.BoolFalse):
        return integer_constant(0)
    elif isinstance(expr, ChironAST.BoolTrue):
        return integer_constant(1)
    else:
        raise TypeError("Unsupported expression type for operand conversion.")
    
def _optimise_unary_arith(op: operator, dest: variable, src: operand) -> statement:
    '''
    Try the following optimisations for unary arithmetic operations:
    - ``x = + x`` can be optimised to ``nop``.
    - ``x = - n`` can be optimised to ``x = + -n``.
    '''

    if op == operator('+') and dest == src:
        return nop_statement()
    
    if op == operator('-') and isinstance(src, integer_constant):
        return assignment_statement(operator('+'), dest, integer_constant(-src.value))
    
    return assignment_statement(op, dest, src)

def _optimise_binary_arith(op: operator, dest: variable, src1: operand, src2: operand) -> statement:
    if isinstance(src1, integer_constant) and isinstance(src2, integer_constant):
        return assignment_statement(operator("+"), dest, integer_constant(eval(f"{src1.value} {op.name} {src2.value}")))
    
    match op:
        case operator(name='+'):
            if src1 == integer_constant(0):
                return _optimise_unary_arith(operator("+"), dest, src2)
            if src2 == integer_constant(0):
                return _optimise_unary_arith(operator("+"), dest, src1)
            
        case operator(name='-'):
            if src1 == integer_constant(0):
                return _optimise_unary_arith(operator('-'), dest, src2)
            
            if src2 == integer_constant(0):
                return _optimise_unary_arith(operator('+'), dest, src1)

        case operator(name='*'):
            if (isinstance(src1, integer_constant) and src1.value == 0) or (isinstance(src2, integer_constant) and src2.value == 0):
                return assignment_statement(operator("+"), dest, integer_constant(0))
            if isinstance(src1, integer_constant) and src1.value in (1, -1):
                return _optimise_unary_arith(operator("+" if src1.value == 1 else "-"), dest, src2)
            if isinstance(src2, integer_constant) and src2.value in (1, -1):
                return _optimise_unary_arith(operator("+" if src2.value == 1 else "-"), dest, src1)
            
    return assignment_statement(op, dest, src1, src2)

def _traverse_arith_expr(expr: ChironAST.ArithExpr, temp_prefix: str, temp_ctr: int = 0) -> Generator[assignment_statement, Any, Any]:
    # We will flatten the arithmetic expression into a sequence of assignment statements
    # using temporary variables. The final variable will be unwound in an
    # assignment statement to the destination variable.
    # We will perform a postorder traversal of the arithmetic expression tree
    # to generate the assignment statements in the correct order.
    if isinstance(expr, ChironAST.UnaryArithOp):
        if isinstance(expr.expr, ChironAST.Value):
            yield assignment_statement(operator(expr.symbol), variable(-1, f"{temp_prefix}{temp_ctr}"), _to_operand(expr.expr))
        else:
            yield from _traverse_arith_expr(expr.expr, temp_prefix, temp_ctr)
            yield assignment_statement(operator(expr.symbol), variable(-1, f"{temp_prefix}{temp_ctr}"), variable(-1, f"{temp_prefix}{temp_ctr}"))
    
    elif isinstance(expr, ChironAST.BinArithOp):
        if isinstance(expr.lexpr, ChironAST.Value):
            src1 = _to_operand(expr.lexpr)
            src2_offset = 0
        elif isinstance(expr.lexpr, ChironAST.ArithExpr):
            yield from _traverse_arith_expr(expr.lexpr, temp_prefix, temp_ctr)
            src1 = variable(-1, f"{temp_prefix}{temp_ctr}")
            src2_offset = 1
        else:
            raise TypeError("Unsupported expression type for arithmetic expression conversion.")
        
        if isinstance(expr.rexpr, ChironAST.Value):
            src2 = _to_operand(expr.rexpr)
        elif isinstance(expr.rexpr, ChironAST.ArithExpr):
            yield from _traverse_arith_expr(expr.rexpr, temp_prefix, temp_ctr + src2_offset)
            src2 = variable(-1, f"{temp_prefix}{temp_ctr + src2_offset}")
        else:
            raise TypeError("Unsupported expression type for arithmetic expression conversion.")
        
        yield assignment_statement(
            operator(expr.symbol),
            variable(-1, f"{temp_prefix}{temp_ctr}"),
            src1,
            src2
        )
    
    else:
        raise TypeError("Unsupported expression type for arithmetic expression conversion.")

def _from_AssignmentCommand(instr: ChironAST.AssignmentCommand, bb_index: int) -> Generator[assignment_statement, Any, Any]:
    dest = variable(-1, instr.lvar.varname)

    if isinstance(instr.rexpr, ChironAST.Value):
        src = _to_operand(instr.rexpr)
        op = operator("+")
        yield assignment_statement(op, dest, src)
    
    elif isinstance(instr.rexpr, (ChironAST.UnaryArithOp, ChironAST.BinArithOp)):
        expr = instr.rexpr
        stmts = list(_traverse_arith_expr(expr, f"__tempL{bb_index}_"))
        stmts[-1].dest = dest
        yield from stmts

    else:
        # Boolean expressions are not assignable, they are only used
        # in branches.
        raise TypeError("Unsupported expression type for assignment statement conversion.")
    
def _traverse_condition_expr(expr: ChironAST.BoolExpr, temp_prefix: str, temp_ctr: int = 0) -> Generator[assignment_statement, Any, Any]:
    if isinstance(expr, ChironAST.BoolExpr):
        # We will flatten the condition into a sequence of assignment statements
        # using temporary variables. The final variable will be
        # unwound in a jump statement to jump to the target.
        # We will perform an postorder traversal of the condition expression tree
        # to generate the assignment statements in the correct order.

        if isinstance(expr, ChironAST.NOT):
            # We will compute the value of the inner condition into a variable,
            # and then compute the value of the NOT operation into the same
            # variable, which is returned.
            if isinstance(expr.expr, (ChironAST.BoolFalse, ChironAST.BoolTrue)):
                yield assignment_statement(operator("not"), variable(-1, f"{temp_prefix}{temp_ctr}"), _to_operand(expr.expr))
            else:
                yield from _traverse_condition_expr(expr.expr, temp_prefix, temp_ctr)
                yield assignment_statement(operator("not"), variable(-1, f"{temp_prefix}{temp_ctr}"), variable(-1, f"{temp_prefix}{temp_ctr}"))   
        elif isinstance(expr, (ChironAST.BinCondOp)):
            # We will compute the values of the left and right subexpressions
            # into variables, and then compute the value of the binary condition
            # operation into one of the variables (reuse), which is returned.
            if isinstance(expr.lexpr, (ChironAST.BoolFalse, ChironAST.BoolTrue, ChironAST.Value)):
                src1 = _to_operand(expr.lexpr)
                src2_offset = 0
            elif isinstance(expr.lexpr, ChironAST.BoolExpr):
                yield from _traverse_condition_expr(expr.lexpr, temp_prefix, temp_ctr)
                src1 = variable(-1, f"{temp_prefix}{temp_ctr}")
                src2_offset = 1
            elif isinstance(expr.lexpr, ChironAST.ArithExpr):
                yield from _traverse_arith_expr(expr.lexpr, temp_prefix, temp_ctr)
                src1 = variable(-1, f"{temp_prefix}{temp_ctr}")
                src2_offset = 1
            else:
                raise TypeError("Unsupported boolean expression type for condition command conversion.")

            if isinstance(expr.rexpr, (ChironAST.BoolFalse, ChironAST.BoolTrue, ChironAST.Value)):
                src2 = _to_operand(expr.rexpr)
            elif isinstance(expr.rexpr, ChironAST.BoolExpr):
                yield from _traverse_condition_expr(expr.rexpr, temp_prefix, temp_ctr + src2_offset)
                src2 = variable(-1, f"{temp_prefix}{temp_ctr + src2_offset}")
            elif isinstance(expr.rexpr, ChironAST.ArithExpr):
                yield from _traverse_arith_expr(expr.rexpr, temp_prefix, temp_ctr + src2_offset)
                src2 = variable(-1, f"{temp_prefix}{temp_ctr + src2_offset}")
            else:
                raise TypeError("Unsupported boolean expression type for condition command conversion.")

            yield assignment_statement(
                operator(expr.symbol),
                variable(-1, f"{temp_prefix}{temp_ctr}"),
                src1,
                src2
            )     
        else:
            raise TypeError("Unsupported boolean expression type for condition command conversion.")

def _negate_condition(expr: ChironAST.BoolExpr) -> ChironAST.BoolExpr:
    '''
    Invert the condition in the given boolean expression
    and return the result (as an AST subtree).
    '''

    op_map = {
        "<": ">=",
        ">": "<=",
        "<=": ">",
        ">=": "<",
        "==": "!=",
        "!=": "=="
    }

    if isinstance(expr, ChironAST.BoolFalse):
        return ChironAST.BoolTrue()
    
    if isinstance(expr, ChironAST.BoolTrue):
        return ChironAST.BoolFalse()

    if isinstance(expr, ChironAST.NOT):
        return expr.expr
    
    if isinstance(expr, ChironAST.BinCondOp):
        if expr.symbol in op_map:
            return ChironAST.BinCondOp(expr.lexpr, expr.rexpr, op_map[expr.symbol])
        
        if expr.symbol in ("and", "or"):
            return ChironAST.NOT(expr)

        raise ValueError("Unsupported boolean operator for condition negation.")

    raise ValueError("Unsupported operator for condition negation.")

def _from_ConditionCommand(instr: ChironAST.ConditionCommand, bb_index: int, target_index: int, fallthrough_index: int)\
      -> Generator[statement, Any, Any]:
    if isinstance(instr, ChironAST.ConditionCommand):
        if isinstance(instr.cond, ChironAST.BoolFalse):
            yield jump_statement(label(target_index))
        
        elif isinstance(instr.cond, ChironAST.BoolTrue):
            yield jump_statement(label(fallthrough_index))
        
        elif isinstance(instr.cond, ChironAST.BoolExpr):
            expr = _negate_condition(instr.cond)
            stmts = list(_traverse_condition_expr(expr, f"__tempL{bb_index}_"))
            jump_stmt = jump_statement(
                target1=label(target_index),
                target2=label(fallthrough_index),
                cond=jump_statement.condition(stmts[-1].op, stmts[-1].src1, stmts[-1].src2)
            )
            yield from stmts[:-1]
            yield jump_stmt

        else:
            raise TypeError("Unsupported condition type for condition command conversion.")
    else:
        raise TypeError("Unsupported instruction type for condition command conversion.")

def _from_MoveCommand(instr: ChironAST.MoveCommand, bb_index: int) -> Generator[statement, Any, Any]:
    if isinstance(instr.expr, ChironAST.Value):
        arg = _to_operand(instr.expr)
    else:
        yield from _traverse_arith_expr(instr.expr, f"__tempL{bb_index}_", 0)
        arg = variable(-1, f"__tempL{bb_index}_0")

    # TODO: Implement syscall_num and syscall_label
    yield push_statement(syscall_num(instr))
    yield push_statement(arg)
    yield syscall_statement()

def _from_PenCommand(instr: ChironAST.PenCommand, bb_index: int) -> Generator[statement, Any, Any]:
    yield push_statement(syscall_num(instr))
    yield syscall_statement()

def _from_GotoCommand(instr: ChironAST.GotoCommand, bb_index: int) -> Generator[statement, Any, Any]:
    if isinstance(instr.xcor, ChironAST.Value):
        arg1 = _to_operand(instr.xcor)
    else:
        yield from _traverse_arith_expr(instr.xcor, f"__tempL{bb_index}_", 0)
        arg1 = variable(-1, f"__tempL{bb_index}_0")

    if isinstance(instr.ycor, ChironAST.Value):
        arg2 = _to_operand(instr.ycor)
    else:
        yield from _traverse_arith_expr(instr.ycor, f"__tempL{bb_index}_", 1)
        arg2 = variable(-1, f"__tempL{bb_index}_1")

    yield push_statement(syscall_num(instr))
    yield push_statement(arg1)
    yield push_statement(arg2)
    yield syscall_statement()

def _to_statement(
    instr: ChironAST.Instruction,
    bb_index: int,
    target_index: int = -1,
    fallthrough_index: int = -1
)-> Generator[statement, Any, Any]:
    '''
    Given an IR instruction, convert it to a sequence of 3AC statements. The
    conversion depends on the type of the instruction and may introduce new
    temporary variables; however, it does not perform variable renaming for
    SSA form.

    :param ChironAST.Instruction instr: The IR instruction to convert.
    :param int bb_index: The index of the basic block containing the
        instruction, used for generating unique temporary variable names
        at the BB level to avoid unnecessary phi-functions.
    :param int target_index: The index of the target basic block for control
        flow instructions. Omitted for non-control flow instructions.
    :param int fallthrough_index: The index of the fallthrough basic block
        for control flow instructions. Omitted for non-control flow
        instructions.
    :return Generator[statement, Any, Any]:
        A generator yielding the 3AC statements corresponding to the given
        IR instruction.
    '''

    if isinstance(instr, ChironAST.AssignmentCommand):
        yield from _from_AssignmentCommand(instr, bb_index)
    
    elif isinstance(instr, ChironAST.ConditionCommand):
        yield from _from_ConditionCommand(instr, bb_index, target_index, fallthrough_index)

    elif isinstance(instr, ChironAST.MoveCommand):
        yield from _from_MoveCommand(instr, bb_index)

    elif isinstance(instr, ChironAST.PenCommand):
        yield from _from_PenCommand(instr, bb_index)

    elif isinstance(instr, ChironAST.GotoCommand):
        yield from _from_GotoCommand(instr, bb_index)

    elif isinstance(instr, ChironAST.NoOpCommand):
        yield nop_statement()

    else:
        raise TypeError("Unsupported instruction type for statement conversion.")

def to_statement(
    instr: tuple[ChironAST.Instruction, int],
    bb_index: int,
    basic_block_boundaries: list[int],
    # line: int
) -> Generator[statement, Any, Any]:
    '''
    Given an IR instruction, convert it to a sequence of 3AC statements. The
    conversion depends on the type of the instruction and may introduce new
    temporary variables; however, it does not perform variable renaming for
    SSA form.

    :param tuple[ChironAST.Instruction, int] instr:
        The IR instruction and its index to convert.
    :param int bb_index: The index of the basic block containing the
        instruction, used for generating unique temporary variable names
        at the BB level to avoid unnecessary phi-functions.
    :param list[int] basic_block_boundaries: The sorted list of indices
        where basic blocks start.
    :param int line: The line number of the instruction in the original IR
        relative to the start of the basic block.
    :return Generator[statement, Any, Any]:
        A generator yielding the 3AC statements corresponding to the given
        IR instruction.
    '''

    if instr[1] == 1:
        if isinstance(instr[0], ChironAST.ConditionCommand):
            # This is a useless instruction, skip. There is anyways
            # no basic block boundary after this instruction.
            return
        else:
            target_index = fallthrough_index = -1
    else:
        # Control flow instruction will be at the end of the BB.
        target_index = basic_block_boundaries.index(basic_block_boundaries[bb_index + 1] - 1 + instr[1])
        # Fallthrough statement will be in the next BB.
        fallthrough_index = bb_index + 1

    yield from _to_statement(instr[0], bb_index, target_index, fallthrough_index)