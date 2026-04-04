from .operands import variable
from .statements import (assignment_statement, jump_statement, pop_statement,
                         push_statement, statement, φ_statement)


def src_variables(stmt: statement) -> list[variable]:
    '''
    Get the source variables (variables used on the right-hand side) of the given statement.
    '''
    
    match stmt:
        case assignment_statement():
            return [src for src in [stmt.src1, stmt.src2] if isinstance(src, variable)]
        case jump_statement():
            if stmt.is_conditional:
                return [src for src in [stmt.cond.src1, stmt.cond.src2] if isinstance(src, variable)]
            else:
                return []
        case push_statement():
            return [stmt.src] if isinstance(stmt.src, variable) else []
        case φ_statement():
            return stmt.srcs
        case _:
            return []
        
def _dest_variable(stmt: statement) -> variable | None:
    '''
    Get the destination variable (variable assigned to on the left-hand side) of the given statement, if any.
    '''
    
    match stmt:
        case assignment_statement():
            return stmt.dest
        case pop_statement():
            return stmt.dest
        case φ_statement():
            return stmt.dest
        case _:
            return None
            
def renumber_variables(
    stmt: statement,
    version: dict[str, int],
    phi_args: dict[str, int],
    phi_targets: dict[str, int],
    seen_vars: set[str]
) -> None:
    '''
    Renumber the variables in the given statement according to the given version mapping.
    This function modifies the statement in place.
    '''
    
    srcs = src_variables(stmt)
    dest = _dest_variable(stmt)

    for src in srcs:
        if src.name not in seen_vars:
            seen_vars.add(src.name)
            version[src.name] = version.get(src.name, -1) + 1
            phi_targets[src.name] = version[src.name]
            
        src.index = version[src.name]

    if dest is not None:
        if dest.name not in seen_vars:
            seen_vars.add(dest.name)

        version[dest.name] = version.get(dest.name, -1) + 1
        dest.index = version[dest.name]
        phi_args[dest.name] = dest.index

    # Notes:
    # - Sources must be iterated over before destinations.
    # 
    # - For sources never seen before, we increment the version since the
    #   version used is the one assigned to by the φ-statement. The
    #   variable is also added to the list of φ-statement targets.
    # 
    # - For destinations never seen before, we simply increment the version
    #   and update the φ-statement argument list for successor BBs to use
    #   the new (last live) version.