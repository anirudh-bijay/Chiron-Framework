# Instruction selection for the MIPS architecture.

import sys
from typing import Generator

import networkx as nx
from ssa.label import label
from ssa.operands import (integer_constant, operand, uninitialised_constant,
                          variable)
from ssa.operators import operator
from ssa.statements import (assignment_statement, jump_statement,
                            nop_statement, push_statement, statement,
                            syscall_statement, φ_statement)

from .instructions import mips_instruction
from .registers import physical_register
from .split import split_critical_edges

clarg_counter = 1
clargs: list[str] = []

def _store_mem(src: operand, base: variable | physical_register, offset: integer_constant) -> Generator[mips_instruction]:
    if isinstance(src, integer_constant):
        if src.value == 0:
            yield mips_instruction('sw', [physical_register('$zero'), base, offset])
        else:
            yield from _assign_temporary(physical_register('$at'), src)
            yield mips_instruction('sw', [physical_register('$at'), base, offset])
    elif isinstance(src, (variable, physical_register)):
        yield mips_instruction('sw', [src, base, offset])
    elif isinstance(src, uninitialised_constant):
        print(f'Omitting store of uninitialised constant to memory at {offset}({base})', file=sys.stderr)
    else:
        raise NotImplementedError(f'Unsupported operand type for store: {type(src)}')
    
def _load_mem(dest: variable | physical_register, base: variable | physical_register, offset: integer_constant) -> Generator[mips_instruction]:
    yield mips_instruction('lw', [dest, base, offset])

def _assign_temporary(dest: variable | physical_register, src1: operand) -> Generator[mips_instruction]:
    if isinstance(src1, integer_constant):
        if 0 <= src1.value < 1 << 16: # Unsigned 16-bit immediate
            yield mips_instruction('ori', [dest, physical_register('$zero'), src1])
        elif -(1 << 15) <= src1.value < 0: # Signed 16-bit immediate
            yield mips_instruction('addiu', [dest, physical_register('$zero'), integer_constant(src1.value)])
        else:
            yield mips_instruction('li', [dest, integer_constant(src1.value)])
    elif isinstance(src1, (variable, physical_register)):
        if src1 == dest:
            return
        yield mips_instruction('move', [dest, src1])
    elif isinstance(src1, uninitialised_constant):
        global clarg_counter
        print(f'Omitting assignment of uninitialised constant to {dest}; loading it from\n'
              f'command-line argument at position {clarg_counter}', file=sys.stderr)
        yield from _load_mem(dest, physical_register('$a1'), integer_constant(4 * clarg_counter))
        clargs.append(dest.name)
        clarg_counter += 1
    else:
        raise NotImplementedError(f'Unsupported operand type for assignment: {type(src1)}')

def _select_unary_assignment(stmt: assignment_statement) -> Generator[mips_instruction]:
    match stmt.op.name:
        case '+':
            if isinstance(stmt.src1, integer_constant):
                if 0 <= stmt.src1.value < 1 << 16: # Unsigned 16-bit immediate
                    yield mips_instruction('ori', [stmt.dest, physical_register('$zero'), stmt.src1])
                elif -(1 << 15) <= stmt.src1.value < 0: # Signed 16-bit immediate
                    yield mips_instruction('addiu', [stmt.dest, physical_register('$zero'), integer_constant(stmt.src1.value)])
                else:
                    yield mips_instruction('li', [stmt.dest, integer_constant(stmt.src1.value)])
            elif isinstance(stmt.src1, (variable, physical_register)):
                if stmt.src1 == stmt.dest:
                    return
                yield mips_instruction('move', [stmt.dest, stmt.src1])
            elif isinstance(stmt.src1, uninitialised_constant):
                global clarg_counter
                print(f'Omitting assignment of uninitialised constant to {stmt.dest}', file=sys.stderr)
                yield from _load_mem(stmt.dest, physical_register('$a1'), integer_constant(4 * clarg_counter))
                clargs.append(stmt.dest.name)
                clarg_counter += 1
            else:
                raise NotImplementedError(f'Unsupported operand type for unary +: {type(stmt.src1)}')
        case '-':
            if isinstance(stmt.src1, integer_constant):
                yield from _select_unary_assignment(assignment_statement(operator('+'), stmt.dest, integer_constant(-stmt.src1.value)))
            elif isinstance(stmt.src1, (variable, physical_register)):
                yield mips_instruction('neg', [stmt.dest, stmt.src1])
            else:
                raise NotImplementedError(f'Unsupported operand type for unary -: {type(stmt.src1)}')
        case 'not':
            if isinstance(stmt.src1, integer_constant):
                yield from _select_unary_assignment(assignment_statement(operator('+'), stmt.dest, integer_constant(int(stmt.src1.value == 0))))
            elif isinstance(stmt.src1, (variable, physical_register)):
                yield mips_instruction('not', [stmt.dest, stmt.src1])
            else:
                raise NotImplementedError(f'Unsupported operand type for unary not: {type(stmt.src1)}')
        case _:
            raise NotImplementedError(f'Unsupported unary operator: {stmt.op}')
        
def _select_binary_assignment(stmt: assignment_statement) -> Generator[mips_instruction]:
    # Very ugly code, but no choice.
    match stmt.op.name:
        case '+':
            if isinstance(stmt.src1, integer_constant):
                if isinstance(stmt.src2, integer_constant):
                    yield from _select_unary_assignment(assignment_statement(operator('+'), stmt.dest, integer_constant(stmt.src1.value + stmt.src2.value)))
                elif isinstance(stmt.src2, (variable, physical_register)):
                    yield from _select_binary_assignment(assignment_statement(operator('+'), stmt.dest, stmt.src2, stmt.src1))
                else:
                    raise NotImplementedError(f'Unsupported operand type for binary +: {type(stmt.src2)}')
            elif isinstance(stmt.src2, integer_constant):
                if -(1 << 15) <= stmt.src2.value < 1 << 15: # Signed 16-bit immediate
                    yield mips_instruction('addiu', [stmt.dest, stmt.src1, integer_constant(stmt.src2.value)])
                else:
                    if stmt.src2.value == 0:
                        phys_reg = physical_register('$zero')
                    else:
                        yield from _assign_temporary(physical_register('$at'), stmt.src2)
                        phys_reg = physical_register('$at')
                    yield mips_instruction('addu', [stmt.dest, stmt.src1, phys_reg])
            elif isinstance(stmt.src2, (variable, physical_register)):
                yield mips_instruction('addu', [stmt.dest, stmt.src1, stmt.src2])
            else:
                raise NotImplementedError(f'Unsupported operand type for binary +: {type(stmt.src2)}')
        case '-':
            if isinstance(stmt.src1, integer_constant):
                if isinstance(stmt.src2, integer_constant):
                    yield from _select_unary_assignment(assignment_statement(operator('+'), stmt.dest, integer_constant(stmt.src1.value - stmt.src2.value)))
                elif isinstance(stmt.src2, (variable, physical_register)):
                    if stmt.src1.value == 0:
                        phys_reg = physical_register('$zero')
                    else:
                        yield from _assign_temporary(physical_register('$at'), integer_constant(stmt.src1.value))
                        phys_reg = physical_register('$at')
                    yield mips_instruction('subu', [stmt.dest, phys_reg, stmt.src2])
                else:
                    raise NotImplementedError(f'Unsupported operand type for binary -: {type(stmt.src2)}')
            elif isinstance(stmt.src2, integer_constant):
                if stmt.src2.value == 0:
                    yield from _select_unary_assignment(assignment_statement(operator('+'), stmt.dest, stmt.src1))
                elif -(1 << 15) < stmt.src2.value < 1 << 15: # Negation of 16-bit 0xFFFF is again 16-bit 0xFFFF, so we exclude it.
                    yield from _select_binary_assignment(assignment_statement(operator('+'), stmt.dest, stmt.src1, integer_constant(-stmt.src2.value)))
                else:
                    yield from _assign_temporary(physical_register('$at'), integer_constant(stmt.src2.value))
                    yield mips_instruction('subu', [stmt.dest, stmt.src1, physical_register('$at')])
            elif isinstance(stmt.src2, (variable, physical_register)):
                yield mips_instruction('subu', [stmt.dest, stmt.src1, stmt.src2])
            else:
                raise NotImplementedError(f'Unsupported operand type for binary -: {type(stmt.src2)}')
        case '*':
            if isinstance(stmt.src1, integer_constant) and isinstance(stmt.src2, integer_constant):
                yield from _select_unary_assignment(assignment_statement(operator('+'), stmt.dest, integer_constant(stmt.src1.value * stmt.src2.value)))
            elif isinstance(stmt.src1, (variable, physical_register)) and isinstance(stmt.src2, integer_constant):
                if stmt.src2.value == 0:
                    yield from _select_unary_assignment(assignment_statement(operator('+'), stmt.dest, integer_constant(0)))
                elif stmt.src2.value == 1:
                    yield from _select_unary_assignment(assignment_statement(operator('+'), stmt.dest, stmt.src1))
                elif stmt.src2.value == -1:
                    yield from _select_unary_assignment(assignment_statement(operator('-'), stmt.dest, stmt.src1))
                elif stmt.src2.value > 0 and (stmt.src2.value & (stmt.src2.value - 1)) == 0: # Power of 2
                    yield mips_instruction('sll', [stmt.dest, stmt.src1, integer_constant(stmt.src2.value.bit_length() - 1)])
                else:
                    yield from _assign_temporary(physical_register('$at'), integer_constant(stmt.src2.value))
                    yield mips_instruction('mul', [stmt.dest, stmt.src1, physical_register('$at')])
            elif isinstance(stmt.src1, integer_constant) and isinstance(stmt.src2, (variable, physical_register)):
                yield from _select_binary_assignment(assignment_statement(operator('*'), stmt.dest, stmt.src2, stmt.src1))
            elif isinstance(stmt.src1, (variable, physical_register)) and isinstance(stmt.src2, (variable, physical_register)):
                yield mips_instruction('mul', [stmt.dest, stmt.src1, stmt.src2])
            else:
                raise NotImplementedError(f'Unsupported operand types for binary *: {type(stmt.src1)}, {type(stmt.src2)}')
        case '/':
            if isinstance(stmt.src1, integer_constant) and isinstance(stmt.src2, integer_constant):
                # May throw ZeroDivisionError.
                yield from _select_unary_assignment(assignment_statement(operator('+'), stmt.dest, integer_constant(stmt.src1.value // stmt.src2.value)))
            elif isinstance(stmt.src1, (variable, physical_register)) and isinstance(stmt.src2, integer_constant):
                if stmt.src2.value == 0:
                    # Programmer wants to bomb the program, let him/her. Don't optimise it away.
                    print(f'Warning: division by zero in {stmt}', file=sys.stderr)
                    phys_reg = physical_register('$zero')
                elif stmt.src2.value == 1:
                    yield from _select_unary_assignment(assignment_statement(operator('+'), stmt.dest, stmt.src1))
                    return
                elif stmt.src2.value == -1:
                    yield from _select_unary_assignment(assignment_statement(operator('-'), stmt.dest, stmt.src1))
                    return
                else:
                    yield from _assign_temporary(physical_register('$at'), integer_constant(stmt.src2.value))
                    phys_reg = physical_register('$at')
                yield mips_instruction('div', [stmt.src1, phys_reg])
                yield mips_instruction('mflo', [stmt.dest])
            elif isinstance(stmt.src1, integer_constant) and isinstance(stmt.src2, (variable, physical_register)):
                if stmt.src1.value == 0:
                    yield from _select_unary_assignment(assignment_statement(operator('+'), stmt.dest, integer_constant(0)))
                else:
                    yield from _assign_temporary(physical_register('$at'), integer_constant(stmt.src1.value))
                    yield mips_instruction('div', [physical_register('$at'), stmt.src2])
                    yield mips_instruction('mflo', [stmt.dest])
            elif isinstance(stmt.src1, (variable, physical_register)) and isinstance(stmt.src2, (variable, physical_register)):
                yield mips_instruction('div', [stmt.src1, stmt.src2])
                yield mips_instruction('mflo', [stmt.dest])
            else:
                raise NotImplementedError(f'Unsupported operand types for binary /: {type(stmt.src1)}, {type(stmt.src2)}')
        case 'and' | 'or':
            if isinstance(stmt.src1, integer_constant) and isinstance(stmt.src2, integer_constant):
                yield from _select_unary_assignment(assignment_statement(operator('+'), stmt.dest, integer_constant(stmt.src1.value & stmt.src2.value if stmt.op.name == 'and' else stmt.src1.value | stmt.src2.value)))
            elif (isinstance(stmt.src1, (variable, physical_register)) and isinstance(stmt.src2, integer_constant)):
                yield mips_instruction(stmt.op.name + 'i', [stmt.dest, stmt.src1, stmt.src2]) # andi/ori
            elif isinstance(stmt.src1, integer_constant) and isinstance(stmt.src2, (variable, physical_register)):
                yield from _select_binary_assignment(assignment_statement(operator('and'), stmt.dest, stmt.src2, stmt.src1))
            elif isinstance(stmt.src1, (variable, physical_register)) and isinstance(stmt.src2, (variable, physical_register)):
                yield mips_instruction(stmt.op.name, [stmt.dest, stmt.src1, stmt.src2]) # and/or
            else:
                raise NotImplementedError(f'Unsupported operand types for binary and: {type(stmt.src1)}, {type(stmt.src2)}')
        case '>' | '<' | '>=' | '<=' | '==' | '!=':
            if isinstance(stmt.src1, integer_constant) and isinstance(stmt.src2, integer_constant):
                yield from _select_unary_assignment(assignment_statement(operator('+'), stmt.dest, integer_constant(eval(f"{stmt.src1.value} {stmt.op.name} {stmt.src2.value}"))))
            elif (isinstance(stmt.src1, (variable, physical_register)) and isinstance(stmt.src2, integer_constant)):
                if stmt.op.name == '<' and -(1 << 15) <= stmt.src2.value < (1 << 15):
                    yield mips_instruction('slti', [stmt.dest, stmt.src1, stmt.src2])
                else:
                    if stmt.src2.value == 0:
                        phys_reg = physical_register('$zero')
                    else:
                        yield from _assign_temporary(physical_register('$at'), stmt.src2)
                        phys_reg = physical_register('$at')
                    op = {'>': 'sgt', '<': 'slt', '>=': 'sge', '<=': 'sle', '==': 'seq', '!=': 'sne'}[stmt.op.name]
                    yield mips_instruction(op, [stmt.dest, stmt.src1, phys_reg])
            elif isinstance(stmt.src1, integer_constant) and isinstance(stmt.src2, (variable, physical_register)):
                if stmt.op.name == '>' and -(1 << 15) <= stmt.src1.value < (1 << 15):
                    yield mips_instruction('slti', [stmt.dest, stmt.src2, stmt.src1])
                else:
                    if stmt.src1.value == 0:
                        phys_reg = physical_register('$zero')
                    else:
                        yield from _assign_temporary(physical_register('$at'), stmt.src1)
                        phys_reg = physical_register('$at')
                    op = {'>': 'sgt', '<': 'slt', '>=': 'sge', '<=': 'sle', '==': 'seq', '!=': 'sne'}[stmt.op.name]
                    yield mips_instruction(op, [stmt.dest, phys_reg, stmt.src2])
            elif isinstance(stmt.src1, (variable, physical_register)) and isinstance(stmt.src2, (variable, physical_register)):
                op = {'>': 'sgt', '<': 'slt', '>=': 'sge', '<=': 'sle', '==': 'seq', '!=': 'sne'}[stmt.op.name]
                yield mips_instruction(op, [stmt.dest, stmt.src1, stmt.src2])
            else:
                raise NotImplementedError(f'Unsupported operand types for binary {stmt.op.name}: {type(stmt.src1)}, {type(stmt.src2)}')
        case _:
            raise NotImplementedError(f'Unsupported binary operator: {stmt.op}')

def _select_assignment(stmt: assignment_statement) -> Generator[mips_instruction]:
    if stmt.src2 is None:
        yield from _select_unary_assignment(stmt)
    else:
        yield from _select_binary_assignment(stmt)

def _select_push(stmt: push_statement, pushes_seen: int) -> Generator[mips_instruction]:
    if pushes_seen == 1:
        yield from _assign_temporary(physical_register('$v0'), stmt.src)
    elif pushes_seen <= 5:
        yield from _assign_temporary(physical_register(f'$a{pushes_seen - 2}'), stmt.src)
    else:
        yield from _store_mem(stmt.src, physical_register('$sp'), integer_constant(-4 * (pushes_seen - 5)))

def _select_jump(stmt: jump_statement) -> Generator[mips_instruction]:
    if not stmt.is_conditional:
        yield mips_instruction('j', [stmt.target])
    elif stmt.cond.op.name == 'not':
        if isinstance(stmt.cond.src1, integer_constant):
            if stmt.cond.src1.value == 0:
                yield from _select_jump(jump_statement(stmt.target1))
            else:
                return  # Fallthrough
        elif isinstance(stmt.cond.src1, (variable, physical_register)):
            yield mips_instruction('beqz', [stmt.cond.src1, stmt.target1])
        else:
            raise NotImplementedError(f'Unsupported operand type for conditional jump condition: {type(stmt.cond.src1)}')
    elif isinstance(stmt.cond.src1, integer_constant) and isinstance(stmt.cond.src2, integer_constant):
        if eval(f"{stmt.cond.src1.value} {stmt.cond.op.name} {stmt.cond.src2.value}"):
            yield from _select_jump(jump_statement(stmt.target1))
        else:
            return  # Fallthrough
    elif isinstance(stmt.cond.src1, (variable, physical_register)) and isinstance(stmt.cond.src2, integer_constant):
        match stmt.cond.op.name:
            case 'and':
                if stmt.cond.src2.value == 0:
                    return  # Fallthrough
                else:
                    yield mips_instruction('bnez', [stmt.cond.src1, stmt.target1])
            case 'or':
                if stmt.cond.src2.value == 0:
                    yield mips_instruction('bnez', [stmt.cond.src1, stmt.target1])
                else:
                    yield from _select_jump(jump_statement(stmt.target1))
            case '==' | '!=' | '<' | '>' | '<=' | '>=':
                if stmt.cond.src2.value == 0:
                    # Only for readability of generated code.
                    if stmt.cond.op.name == '==':
                        yield mips_instruction('beqz', [stmt.cond.src1, stmt.target1])
                    elif stmt.cond.op.name == '!=':
                        yield mips_instruction('bnez', [stmt.cond.src1, stmt.target1])
                    else:
                        op = {'>': 'bgt', '<': 'blt', '>=': 'bge', '<=': 'ble'}[stmt.cond.op.name]
                        yield mips_instruction(op, [stmt.cond.src1, physical_register('$zero'), stmt.target1])
                else:
                    yield from _assign_temporary(physical_register('$at'), stmt.cond.src2)
                    op = {'==': 'beq', '!=': 'bne', '>': 'bgt', '<': 'blt', '>=': 'bge', '<=': 'ble'}[stmt.cond.op.name]
                    yield mips_instruction(op, [stmt.cond.src1, physical_register('$at'), stmt.target1])
            case _:
                raise NotImplementedError(f'Unsupported operator for conditional jump: {stmt.cond.op}')
    elif isinstance(stmt.cond.src1, integer_constant) and isinstance(stmt.cond.src2, (variable, physical_register)):
        op = {'and': 'and', 'or': 'or', '==': '==', '!=': '!=', '>': '<', '<': '>', '>=': '<=', '<=': '>='}[stmt.cond.op.name]
        yield from _select_jump(jump_statement(stmt.target1, cond=jump_statement.condition(operator(stmt.cond.op.name), stmt.cond.src2, stmt.cond.src1)))
    elif isinstance(stmt.cond.src1, (variable, physical_register)) and isinstance(stmt.cond.src2, (variable, physical_register)):
        if stmt.cond.op.name in {'and', 'or'}:
            yield mips_instruction(stmt.cond.op.name, [physical_register('$at'), stmt.cond.src1, stmt.cond.src2])
            yield mips_instruction('bnez', [physical_register('$at'), stmt.target1])
        else:
            op = {'==': 'beq', '!=': 'bne', '>': 'bgt', '<': 'blt', '>=': 'bge', '<=': 'ble'}[stmt.cond.op.name]
            yield mips_instruction(op, [stmt.cond.src1, stmt.cond.src2, stmt.target1])
    else:
        raise NotImplementedError(f'Unsupported operand types for conditional jump condition: {type(stmt.cond.src1)}, {type(stmt.cond.src2)}')

pushes_seen: int = 0

def _select_instruction(ssa_statement: statement) -> Generator[mips_instruction]:
    '''
    Select MIPS instructions for a given 3AC statement.

    :param statement ssa_statement: The 3AC statement to select instructions for.
    :return mips_instruction: The selected MIPS instructions.
    '''

    match ssa_statement:
        case assignment_statement():
            yield from _select_assignment(ssa_statement)
        
        case push_statement():
            global pushes_seen
            pushes_seen += 1
            yield from _select_push(ssa_statement, pushes_seen)

        case syscall_statement():
            yield mips_instruction('syscall')
            pushes_seen = 0

        case jump_statement():
            yield from _select_jump(ssa_statement)

        case nop_statement():
            yield mips_instruction('nop')

        # We do not handle pop statements for the time being.

        case _:
            raise NotImplementedError(f'Unsupported statement type for instruction selection: {type(ssa_statement)}')

def mips_from_tac_cfg(cfg: nx.DiGraph[label]) -> list[str]:
    '''
    Convert the 3AC statements in an SSA CFG to MIPS assembly code.

    :param networkx.DiGraph[label] cfg: The control flow graph.
    :return list[str]:
        The list of command-line arguments corresponding to uninitialised
        constants, in the position they should appear on the command line.
    '''

    split_critical_edges(cfg)

    for label, node in cfg.nodes(data=True):
        instructions: list[mips_instruction | φ_statement] = []
        for stmt in node["basic_block"].instructions:
            if isinstance(stmt, φ_statement):
                # Keep them as-is, they will be handled by out-of-SSA.
                instructions.append(stmt)
            else:
                instructions.extend(_select_instruction(stmt))
        node["basic_block"].instructions = instructions

    return clargs